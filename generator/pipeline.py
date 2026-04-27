"""End-to-end pipeline: БТ + БП + Features → docs + src + tests + README."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Optional

from .config import STEP_MODELS, Config
from .io_utils import TaskInput, clean_output, load_task, write_files, write_text
from .llm import LLMClient
from .parser import parse_files_strict

ProgressCallback = Callable[[dict[str, Any]], None]

log = logging.getLogger("generator.pipeline")

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def _load_prompt(name: str) -> tuple[str, str]:
    """Load a prompt file and split it into (system, user)."""
    text = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    if "# USER" not in text or "# SYSTEM" not in text:
        raise ValueError(f"Prompt {name} missing # SYSTEM or # USER header")
    parts = text.split("# USER", 1)
    system = parts[0].replace("# SYSTEM", "").strip()
    user = parts[1].strip()
    return system, user


def _resolve_model(cfg: Config, step: str) -> str:
    tier = STEP_MODELS.get(step, "fast")
    return cfg.model_smart if tier == "smart" else cfg.model_fast


def _strip_code_fences(text: str) -> str:
    """Remove a single outer markdown fence if the model wrapped the file."""
    s = text.strip()
    if s.startswith("```"):
        first_nl = s.find("\n")
        if first_nl > 0:
            s = s[first_nl + 1 :]
        if s.endswith("```"):
            s = s[: -3].rstrip()
    return s


# ---------- individual steps ----------

def step_use_cases(client: LLMClient, task: TaskInput) -> str:
    system, user_tpl = _load_prompt("use_cases")
    user = user_tpl.replace("{context}", task.as_context())
    text = client.generate(
        step="use_cases",
        model=_resolve_model(client.cfg, "use_cases"),
        system=system,
        user=user,
        temperature=0.3,
        max_output_tokens=8192,
    )
    return _strip_code_fences(text)


def step_nfr(client: LLMClient, task: TaskInput) -> str:
    system, user_tpl = _load_prompt("nfr")
    user = user_tpl.replace("{context}", task.as_context())
    text = client.generate(
        step="nfr",
        model=_resolve_model(client.cfg, "nfr"),
        system=system,
        user=user,
        temperature=0.4,
        max_output_tokens=4096,
    )
    return _strip_code_fences(text)


def step_fr(
    client: LLMClient, task: TaskInput, use_cases: str, nfr: str
) -> str:
    system, user_tpl = _load_prompt("fr")
    user = (
        user_tpl
        .replace("{context}", task.as_context())
        .replace("{use_cases}", use_cases)
        .replace("{nfr}", nfr)
    )
    text = client.generate(
        step="fr",
        model=_resolve_model(client.cfg, "fr"),
        system=system,
        user=user,
        temperature=0.3,
        max_output_tokens=8192,
    )
    return _strip_code_fences(text)


def step_code(
    client: LLMClient,
    task: TaskInput,
    use_cases: str,
    nfr: str,
    fr: str,
) -> dict[str, str]:
    system, user_tpl = _load_prompt("code")
    user = (
        user_tpl
        .replace("{context}", task.as_context())
        .replace("{use_cases}", use_cases)
        .replace("{nfr}", nfr)
        .replace("{fr}", fr)
    )
    text = client.generate(
        step="code",
        model=_resolve_model(client.cfg, "code"),
        system=system,
        user=user,
        temperature=0.4,
        max_output_tokens=16384,
    )
    files = parse_files_strict(text)
    # Validate at least index.html and one js
    if not any(p.endswith("index.html") for p in files):
        raise ValueError(
            f"Code generation missing src/index.html. Got: {sorted(files)}"
        )
    return files


def step_tests(
    client: LLMClient, fr: str, code_files: dict[str, str]
) -> dict[str, str]:
    # Build a lightweight listing of generated source code (paths + first ~40 lines)
    listing_parts = []
    for p, content in code_files.items():
        if not p.startswith("src/") or not p.endswith(".js"):
            continue
        head = "\n".join(content.splitlines()[:60])
        listing_parts.append(f"### {p}\n```javascript\n{head}\n```")
    code_listing = "\n\n".join(listing_parts) if listing_parts else "(нет JS-модулей)"

    system, user_tpl = _load_prompt("tests")
    user = (
        user_tpl
        .replace("{fr}", fr)
        .replace("{code_listing}", code_listing)
    )
    text = client.generate(
        step="tests",
        model=_resolve_model(client.cfg, "tests"),
        system=system,
        user=user,
        temperature=0.3,
        max_output_tokens=8192,
    )
    return parse_files_strict(text)


def step_readme(
    client: LLMClient,
    task: TaskInput,
    code_files: dict[str, str],
    test_files: dict[str, str],
) -> str:
    file_list = "\n".join(f"- `{p}`" for p in sorted(code_files))
    test_list = "\n".join(f"- `{p}`" for p in sorted(test_files)) or "(тесты не сгенерированы)"
    system, user_tpl = _load_prompt("readme")
    user = (
        user_tpl
        .replace("{context}", task.as_context())
        .replace("{file_list}", file_list)
        .replace("{test_list}", test_list)
    )
    text = client.generate(
        step="readme",
        model=_resolve_model(client.cfg, "readme"),
        system=system,
        user=user,
        temperature=0.3,
        max_output_tokens=4096,
    )
    return _strip_code_fences(text)


# ---------- orchestrator ----------

def run_pipeline(
    *,
    cfg: Config,
    input_dir: Path,
    output_dir: Path,
    skip_use_cases: bool = False,
    skip_tests: bool = False,
    on_event: Optional[ProgressCallback] = None,
) -> dict[str, object]:
    """Run the full cascade. Returns a small report dict.

    on_event(payload): optional callback fired at each step with payload like:
        {type: "start" | "step_start" | "step_done" | "done", step?, index?, total?, ...}
    """

    def emit(event_type: str, **payload: Any) -> None:
        if on_event:
            try:
                on_event({"type": event_type, **payload})
            except Exception:
                log.exception("on_event callback raised — ignoring")

    log.info("Loading input from %s", input_dir)
    task = load_task(input_dir)
    total_steps = 6 - int(skip_use_cases) - int(skip_tests)
    emit("start", task=task.name, total=total_steps,
         provider=cfg.provider, model_fast=cfg.model_fast, model_smart=cfg.model_smart)

    log.info("Cleaning output dir %s", output_dir)
    clean_output(output_dir)
    (output_dir / "docs").mkdir(parents=True, exist_ok=True)

    step_index = 0

    def begin(name: str) -> int:
        nonlocal step_index
        step_index += 1
        emit("step_start", step=name, index=step_index, total=total_steps)
        log.info("[%d/%d] Generating %s ...", step_index, total_steps, name)
        return step_index

    with LLMClient(cfg) as client:
        # 1. Use cases (optional)
        use_cases = ""
        if not skip_use_cases:
            begin("use_cases")
            use_cases = step_use_cases(client, task)
            write_text(output_dir / "docs" / "use-cases.md", use_cases)
            emit("step_done", step="use_cases", chars=len(use_cases),
                 path="docs/use-cases.md")

        # 2. NFR
        begin("nfr")
        nfr = step_nfr(client, task)
        write_text(output_dir / "docs" / "non-functional-req.md", nfr)
        emit("step_done", step="nfr", chars=len(nfr),
             path="docs/non-functional-req.md")

        # 3. FR (with traceability to BT, UC, Features)
        begin("fr")
        fr = step_fr(client, task, use_cases, nfr)
        write_text(output_dir / "docs" / "functional-req.md", fr)
        emit("step_done", step="fr", chars=len(fr),
             path="docs/functional-req.md")

        # 4. Source code
        begin("code")
        code_files = step_code(client, task, use_cases, nfr, fr)
        write_files(output_dir, code_files)
        log.info("    wrote %d source files", len(code_files))
        emit("step_done", step="code", file_count=len(code_files),
             paths=sorted(code_files.keys()))

        # 5. Tests
        test_files: dict[str, str] = {}
        if not skip_tests:
            begin("tests")
            test_files = step_tests(client, fr, code_files)
            write_files(output_dir, test_files)
            log.info("    wrote %d test files", len(test_files))
            emit("step_done", step="tests", file_count=len(test_files),
                 paths=sorted(test_files.keys()))

        # 6. README
        begin("readme")
        readme = step_readme(client, task, code_files, test_files)
        write_text(output_dir / "README.md", readme)
        emit("step_done", step="readme", chars=len(readme), path="README.md")

        # Persist usage summary
        summary_path = output_dir / "_generator_log.md"
        summary_path.write_text(
            "# Generator log\n\n"
            f"- Task: `{task.name}`\n"
            f"- Provider: `{cfg.provider}`\n"
            f"- Model fast: `{cfg.model_fast}`\n"
            f"- Model smart: `{cfg.model_smart}`\n\n"
            "## Token usage\n\n```\n" + client.usage.summary() + "\n```\n",
            encoding="utf-8",
        )

        files_generated = len(code_files) + len(test_files) + 4
        emit(
            "done",
            files=files_generated,
            input_tokens=client.usage.input_tokens,
            output_tokens=client.usage.output_tokens,
            calls=client.usage.calls,
        )

        return {
            "task": task.name,
            "files_generated": files_generated,
            "usage": client.usage,
        }

"""End-to-end pipeline: БТ + БП + Features → docs + src + tests + README."""
from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Optional

from .config import STEP_MODELS, Config
from .io_utils import TaskInput, clean_output, load_task, write_files, write_text
from .llm import LLMClient
from .parser import parse_files_strict
from .validators import (
    ValidationReport,
    validate_code,
    validate_fr,
    validate_use_cases,
)

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


def _resolve_model(cfg: Config, step: str, overrides: Optional[dict[str, str]] = None) -> str:
    """Pick the model for a given step.

    overrides may contain:
        {"fast": "...", "smart": "..."}  — tier overrides
        {"<step_name>": "..."}            — per-step override (takes precedence)
    """
    overrides = overrides or {}
    if step in overrides and overrides[step]:
        return overrides[step]
    tier = STEP_MODELS.get(step, "fast")
    if tier in overrides and overrides[tier]:
        return overrides[tier]
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

def _with_feedback(user: str, feedback: str) -> str:
    """Append feedback to the user prompt for a retry pass."""
    if not feedback:
        return user
    return user + (
        "\n\n---\n\n"
        "## ВНИМАНИЕ: предыдущий ответ был неполным\n"
        f"{feedback}\n"
        "Верни обновлённую версию файла целиком, ничего не пропускай. "
        "Сохрани всё что было хорошо, добавь недостающее."
    )


def step_use_cases(
    client: LLMClient, task: TaskInput,
    overrides: Optional[dict[str, str]] = None,
    feedback: str = "",
) -> str:
    system, user_tpl = _load_prompt("use_cases")
    user = _with_feedback(user_tpl.replace("{context}", task.as_context()), feedback)
    text = client.generate(
        step="use_cases",
        model=_resolve_model(client.cfg, "use_cases", overrides),
        system=system,
        user=user,
        temperature=0.3,
        max_output_tokens=8192,
    )
    return _strip_code_fences(text)


def step_nfr(
    client: LLMClient, task: TaskInput,
    overrides: Optional[dict[str, str]] = None,
    feedback: str = "",
) -> str:
    system, user_tpl = _load_prompt("nfr")
    user = _with_feedback(user_tpl.replace("{context}", task.as_context()), feedback)
    text = client.generate(
        step="nfr",
        model=_resolve_model(client.cfg, "nfr", overrides),
        system=system,
        user=user,
        temperature=0.4,
        max_output_tokens=4096,
    )
    return _strip_code_fences(text)


def step_fr(
    client: LLMClient, task: TaskInput, use_cases: str, nfr: str,
    overrides: Optional[dict[str, str]] = None,
    feedback: str = "",
) -> str:
    system, user_tpl = _load_prompt("fr")
    user = (
        user_tpl
        .replace("{context}", task.as_context())
        .replace("{use_cases}", use_cases)
        .replace("{nfr}", nfr)
    )
    user = _with_feedback(user, feedback)
    text = client.generate(
        step="fr",
        model=_resolve_model(client.cfg, "fr", overrides),
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
    overrides: Optional[dict[str, str]] = None,
    feedback: str = "",
    on_chunk: Optional[Callable[[str], None]] = None,
) -> dict[str, str]:
    system, user_tpl = _load_prompt("code")
    user = (
        user_tpl
        .replace("{context}", task.as_context())
        .replace("{use_cases}", use_cases)
        .replace("{nfr}", nfr)
        .replace("{fr}", fr)
    )
    user = _with_feedback(user, feedback)
    model = _resolve_model(client.cfg, "code", overrides)
    if on_chunk:
        text = client.generate_stream(
            step="code", model=model, system=system, user=user,
            temperature=0.4, max_output_tokens=16384, on_chunk=on_chunk,
        )
    else:
        text = client.generate(
            step="code", model=model, system=system, user=user,
            temperature=0.4, max_output_tokens=16384,
        )
    files = parse_files_strict(text)
    # Validate at least index.html and one js
    if not any(p.endswith("index.html") for p in files):
        raise ValueError(
            f"Code generation missing src/index.html. Got: {sorted(files)}"
        )
    return files


def step_tests(
    client: LLMClient, fr: str, code_files: dict[str, str],
    overrides: Optional[dict[str, str]] = None,
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
        model=_resolve_model(client.cfg, "tests", overrides),
        system=system,
        user=user,
        temperature=0.3,
        max_output_tokens=8192,
    )
    return parse_files_strict(text)


def step_refine(
    client: LLMClient,
    code_files: dict[str, str],
    fr: str,
    comment: str,
    overrides: Optional[dict[str, str]] = None,
) -> dict[str, str]:
    """Refinement: take existing code + user comment → patched files.

    Returns a dict of CHANGED files only. Caller merges with previous code.
    """
    listing_parts = []
    for path, content in code_files.items():
        listing_parts.append(f"### {path}\n```\n{content}\n```")
    code_listing = "\n\n".join(listing_parts)

    system, user_tpl = _load_prompt("refine")
    user = (
        user_tpl
        .replace("{code_listing}", code_listing)
        .replace("{fr}", fr)
        .replace("{comment}", comment.strip())
    )
    text = client.generate(
        step="refine",
        model=_resolve_model(client.cfg, "code", overrides),  # use smart tier
        system=system,
        user=user,
        temperature=0.3,
        max_output_tokens=16384,
    )
    return parse_files_strict(text)


def step_readme(
    client: LLMClient,
    task: TaskInput,
    code_files: dict[str, str],
    test_files: dict[str, str],
    overrides: Optional[dict[str, str]] = None,
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
        model=_resolve_model(client.cfg, "readme", overrides),
        system=system,
        user=user,
        temperature=0.3,
        max_output_tokens=4096,
    )
    return _strip_code_fences(text)


# ---------- orchestrator ----------

def run_refinement(
    *,
    cfg: Config,
    output_dir: Path,
    comment: str,
    on_event: Optional[ProgressCallback] = None,
    model_overrides: Optional[dict[str, str]] = None,
) -> dict[str, object]:
    """Re-run only the code step on an existing output dir, applying a user comment.

    Reads `output_dir/src/*` and `output_dir/docs/functional-req.md`,
    asks the LLM to produce changed files only, then merges them back into src/.
    Old files NOT mentioned in the response are preserved.
    """
    src_dir = output_dir / "src"
    fr_path = output_dir / "docs" / "functional-req.md"
    if not src_dir.exists():
        raise FileNotFoundError(f"src/ not found in {output_dir} — run pipeline first")
    if not fr_path.exists():
        raise FileNotFoundError(f"docs/functional-req.md not found — run pipeline first")

    def emit(t: str, **payload: Any) -> None:
        if on_event:
            try:
                on_event({"type": t, **payload})
            except Exception:
                log.exception("on_event callback raised — ignoring")

    code_files: dict[str, str] = {}
    for p in sorted(src_dir.rglob("*")):
        if p.is_file():
            rel = "src/" + p.relative_to(src_dir).as_posix()
            code_files[rel] = p.read_text(encoding="utf-8", errors="replace")
    fr = fr_path.read_text(encoding="utf-8")

    emit("start", task=output_dir.name, total=1, refinement=True,
         provider=cfg.provider, model_fast=cfg.model_fast,
         model_smart=(model_overrides or {}).get("smart", cfg.model_smart),
         comment=comment)
    emit("step_start", step="refine", index=1, total=1)

    log.info("Refinement: comment=%r, %d existing files", comment[:80], len(code_files))

    with LLMClient(cfg) as client:
        try:
            patched = step_refine(client, code_files, fr, comment, model_overrides)
        except Exception as e:
            emit("error", error=str(e), step="refine")
            raise

        # Merge patched files into existing
        merged = {**code_files, **patched}
        # Write only changed files (so the FS reflects the diff cleanly)
        for path, content in patched.items():
            target = output_dir / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

        emit("step_done", step="refine", file_count=len(patched),
             paths=sorted(patched.keys()))

        # Append a refinement entry to the log
        log_path = output_dir / "_generator_log.md"
        if log_path.exists():
            log_path.write_text(
                log_path.read_text(encoding="utf-8")
                + f"\n## Refinement\n- Comment: {comment.strip()!r}\n"
                + f"- Changed files: {', '.join(sorted(patched.keys()))}\n"
                + f"- Tokens: in={client.usage.input_tokens}, out={client.usage.output_tokens}\n",
                encoding="utf-8",
            )

        emit("done",
             files=len(patched),
             input_tokens=client.usage.input_tokens,
             output_tokens=client.usage.output_tokens,
             calls=client.usage.calls,
             refinement=True)

        return {
            "task": output_dir.name,
            "files_generated": len(patched),
            "usage": client.usage,
            "patched_files": sorted(patched.keys()),
        }


def run_pipeline(
    *,
    cfg: Config,
    input_dir: Path,
    output_dir: Path,
    skip_use_cases: bool = False,
    skip_tests: bool = False,
    on_event: Optional[ProgressCallback] = None,
    model_overrides: Optional[dict[str, str]] = None,
    self_check: bool = True,
    max_check_retries: int = 2,
) -> dict[str, object]:
    """Run the full cascade. Returns a small report dict.

    on_event(payload): optional callback fired at each step with payload like:
        {type: "start" | "step_start" | "step_done" | "done", step?, index?, total?, ...}

    model_overrides: optional per-tier or per-step model overrides, e.g.
        {"fast": "qwen/qwen-2.5-7b-instruct", "smart": "deepseek/deepseek-chat-v3-0324"}
        or {"code": "anthropic/claude-3.5-haiku"} for fine-grained control.

    self_check: if True (default), validates ФТ coverage of БТ and code coverage of ФТ
        after generation. If validation fails, re-prompts the LLM up to `max_check_retries`
        times with the missing items as feedback. This significantly improves traceability.
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

    # Resolve effective models for telemetry
    effective_fast = (model_overrides or {}).get("fast", cfg.model_fast)
    effective_smart = (model_overrides or {}).get("smart", cfg.model_smart)
    emit("start", task=task.name, total=total_steps,
         provider=cfg.provider, model_fast=effective_fast, model_smart=effective_smart)

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

    self_check_log: list[dict] = []  # used in _generator_log.md

    def _retry_with_check(name: str, gen_fn, validate_fn) -> any:
        """Run gen_fn with validate-then-retry loop. Returns the final result."""
        feedback = ""
        result = None
        for attempt in range(max_check_retries + 1):
            result = gen_fn(feedback)
            if not self_check:
                return result
            report: ValidationReport = validate_fn(result)
            if report.ok:
                if attempt > 0:
                    log.info("    [%s] self-check ok after retry %d", name, attempt)
                    self_check_log.append({"step": name, "result": "passed_after_retry", "attempts": attempt + 1})
                    emit("self_check_pass", step=name, attempt=attempt + 1)
                else:
                    self_check_log.append({"step": name, "result": "passed_first_try"})
                return result
            log.warning("    [%s] self-check failed (attempt %d/%d): missing %s",
                        name, attempt + 1, max_check_retries + 1, report.missing)
            emit("self_check_retry", step=name, attempt=attempt + 1,
                 missing=report.missing[:10])
            feedback = report.feedback
        # Out of retries — log and return last result anyway
        log.warning("    [%s] self-check exhausted retries; missing %s", name, report.missing)
        self_check_log.append({"step": name, "result": "missing_after_retries",
                               "missing": report.missing})
        emit("self_check_fail", step=name, missing=report.missing[:10])
        return result

    with LLMClient(cfg) as client:
        # 1+2. Use cases & NFR in parallel — both depend only on input.
        # We still emit step_start/step_done in pipeline order so the UI shows
        # them sequentially even though they run concurrently underneath.
        use_cases = ""
        nfr = ""

        def _do_use_cases() -> str:
            return _retry_with_check(
                "use_cases",
                lambda fb: step_use_cases(client, task, model_overrides, fb),
                lambda result: validate_use_cases(result, task.business_requirements),
            )

        def _do_nfr() -> str:
            return step_nfr(client, task, model_overrides)

        if skip_use_cases:
            # Only NFR — no parallelism needed.
            begin("nfr")
            nfr = _do_nfr()
            write_text(output_dir / "docs" / "non-functional-req.md", nfr)
            emit("step_done", step="nfr", chars=len(nfr),
                 path="docs/non-functional-req.md")
        else:
            # Mark both as starting up front so the UI shows the parallelism
            step_index += 1
            emit("step_start", step="use_cases", index=step_index, total=total_steps)
            step_index += 1
            emit("step_start", step="nfr", index=step_index, total=total_steps)
            log.info("[%d/%d] Generating use_cases + nfr (parallel) ...",
                     step_index, total_steps)

            with ThreadPoolExecutor(max_workers=2, thread_name_prefix="cascade-doc") as pool:
                fut_uc = pool.submit(_do_use_cases)
                fut_nfr = pool.submit(_do_nfr)
                # Wait for both. Whichever finishes first emits step_done first.
                results: dict[str, tuple[Any, Optional[Exception]]] = {}
                from concurrent.futures import as_completed
                fut_to_name = {fut_uc: "use_cases", fut_nfr: "nfr"}
                for fut in as_completed(fut_to_name):
                    name = fut_to_name[fut]
                    try:
                        results[name] = (fut.result(), None)
                    except Exception as e:
                        results[name] = (None, e)

            # Re-raise the first error if any
            for name, (_, err) in results.items():
                if err:
                    raise err

            use_cases, _ = results["use_cases"]
            nfr, _ = results["nfr"]
            write_text(output_dir / "docs" / "use-cases.md", use_cases)
            emit("step_done", step="use_cases", chars=len(use_cases),
                 path="docs/use-cases.md")
            write_text(output_dir / "docs" / "non-functional-req.md", nfr)
            emit("step_done", step="nfr", chars=len(nfr),
                 path="docs/non-functional-req.md")

        # 3. FR (with traceability check: every required БТ must be referenced)
        begin("fr")
        fr = _retry_with_check(
            "fr",
            lambda fb: step_fr(client, task, use_cases, nfr, model_overrides, fb),
            lambda result: validate_fr(result, task.business_requirements),
        )
        write_text(output_dir / "docs" / "functional-req.md", fr)
        emit("step_done", step="fr", chars=len(fr),
             path="docs/functional-req.md")

        # 4. Source code (streaming + traceability check: every ФТ → @implements)
        begin("code")

        # Buffered chunk emitter — flush every ~512 chars or on whitespace burst,
        # so the SSE stream doesn't get spammed with single-token events.
        chunk_buf: list[str] = []
        chunk_lock = threading.Lock()
        last_flush_len = [0]

        def _on_chunk(piece: str) -> None:
            with chunk_lock:
                chunk_buf.append(piece)
                total = sum(len(p) for p in chunk_buf)
                # Flush every ~256 chars OR when we get a newline burst
                if total - last_flush_len[0] >= 256 or piece.endswith("\n\n"):
                    text = "".join(chunk_buf)
                    last_flush_len[0] = total
                    emit("step_chunk", step="code", text=text)

        code_files = _retry_with_check(
            "code",
            lambda fb: step_code(client, task, use_cases, nfr, fr,
                                 model_overrides, fb, on_chunk=_on_chunk),
            lambda result: validate_code(result, fr),
        )
        write_files(output_dir, code_files)
        log.info("    wrote %d source files", len(code_files))
        emit("step_done", step="code", file_count=len(code_files),
             paths=sorted(code_files.keys()))

        # 5. Tests
        test_files: dict[str, str] = {}
        if not skip_tests:
            begin("tests")
            test_files = step_tests(client, fr, code_files, model_overrides)
            write_files(output_dir, test_files)
            log.info("    wrote %d test files", len(test_files))
            emit("step_done", step="tests", file_count=len(test_files),
                 paths=sorted(test_files.keys()))

        # 6. README
        begin("readme")
        readme = step_readme(client, task, code_files, test_files, model_overrides)
        write_text(output_dir / "README.md", readme)
        emit("step_done", step="readme", chars=len(readme), path="README.md")

        # Persist usage summary + self-check log
        summary_path = output_dir / "_generator_log.md"
        sc_lines = []
        if self_check:
            sc_lines.append("\n## Self-check\n")
            if not self_check_log:
                sc_lines.append("- (нет записей; шаги пропущены)\n")
            for entry in self_check_log:
                step = entry["step"]
                result = entry["result"]
                if result == "passed_first_try":
                    sc_lines.append(f"- ✅ `{step}`: прошёл с первого раза\n")
                elif result == "passed_after_retry":
                    sc_lines.append(
                        f"- ♻️ `{step}`: прошёл за {entry['attempts']} попыток\n"
                    )
                else:
                    miss = ", ".join(entry.get("missing", [])[:5])
                    sc_lines.append(f"- ⚠️ `{step}`: остались непокрытыми: {miss}\n")
        else:
            sc_lines.append("\n## Self-check\n- отключён (`self_check=False`)\n")

        summary_path.write_text(
            "# Generator log\n\n"
            f"- Task: `{task.name}`\n"
            f"- Provider: `{cfg.provider}`\n"
            f"- Model fast: `{effective_fast}`\n"
            f"- Model smart: `{effective_smart}`\n\n"
            "## Token usage\n\n```\n" + client.usage.summary() + "\n```\n"
            + "".join(sc_lines),
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

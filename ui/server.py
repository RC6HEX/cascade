"""FastAPI web UI for the generator.

Run:
    python -m ui            # uses default host/port (127.0.0.1:8000)
    python -m ui --port 9000

Endpoints:
    GET  /                          → static frontend
    GET  /api/presets               → list of preset tasks (A, B, C)
    GET  /api/preset/{name}         → preset's БТ + БП + Features
    POST /api/jobs                  → create generation job, returns {id}
    GET  /api/jobs/{id}/stream      → SSE: progress events
    GET  /api/jobs/{id}             → current state (polling fallback)
    GET  /api/jobs/{id}/files       → tree of generated files
    GET  /api/jobs/{id}/file?path=  → single file content
    GET  /api/jobs/{id}/zip         → zip download of full output
"""
from __future__ import annotations

import asyncio
import io
import json
import logging
import re
import shutil
import tempfile
import threading
import uuid
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from generator.config import Config, models_for_provider
from generator.io_utils import TaskInput, clean_output, write_text
from generator.pipeline import run_pipeline, run_refinement

log = logging.getLogger("ui.server")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_ROOT = PROJECT_ROOT / "input"
JOBS_ROOT = PROJECT_ROOT / "output" / "_ui_jobs"
JOBS_ROOT.mkdir(parents=True, exist_ok=True)
STATIC_DIR = Path(__file__).resolve().parent / "static"


# ---------- in-memory job state ----------

@dataclass
class Job:
    id: str
    status: str = "pending"  # pending | running | done | error
    output_dir: Path = field(default_factory=lambda: Path())
    events: list[dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    loop: Optional[asyncio.AbstractEventLoop] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status,
            "events": self.events,
            "error": self.error,
        }


JOBS: dict[str, Job] = {}


def _scan_disk_jobs() -> None:
    """On startup, register every artifacts/ folder we can find on disk
    as a 'done' job, so the UI can browse history across restarts.
    """
    if not JOBS_ROOT.exists():
        return
    for child in sorted(JOBS_ROOT.iterdir()):
        if not child.is_dir() or len(child.name) < 6:
            continue
        if not (child / "artifacts").exists():
            continue
        if child.name in JOBS:
            continue
        job = Job(id=child.name, status="done", output_dir=child)
        # Try to load saved meta if exists
        meta_path = child / "_job_meta.json"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                job.events = meta.get("events", [])
            except Exception:
                pass
        JOBS[child.name] = job


def _save_job_meta(job: Job) -> None:
    """Persist a job's event log to disk so we can restore on restart."""
    try:
        meta_path = job.output_dir / "_job_meta.json"
        meta_path.write_text(
            json.dumps({
                "id": job.id,
                "status": job.status,
                "events": job.events,
                "error": job.error,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        log.exception("Failed to save job meta for %s", job.id)


# ---------- request/response models ----------

class GenerateRequest(BaseModel):
    business_requirements: str = Field(min_length=10)
    business_process: str = Field(min_length=10)
    features: Optional[str] = None
    skip_use_cases: bool = False
    skip_tests: bool = False
    self_check: bool = True
    # Live model overrides — let the user pick from UI dropdowns
    model_fast: Optional[str] = None
    model_smart: Optional[str] = None
    # Per-step model overrides (advanced) — keys: use_cases | nfr | fr | code | tests | readme
    per_step_models: Optional[dict[str, str]] = None


class RefineRequest(BaseModel):
    comment: str = Field(min_length=3)
    model_smart: Optional[str] = None


# ---------- app ----------

app = FastAPI(title="Autonomous Generator UI", version="0.1.0")


@app.on_event("startup")
async def _on_startup() -> None:
    _scan_disk_jobs()
    log.info("Loaded %d job(s) from disk", len(JOBS))


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    html_path = STATIC_DIR / "index.html"
    if not html_path.exists():
        raise HTTPException(status_code=500, detail="index.html missing")
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


# Serve other static assets
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/api/presets")
async def list_presets() -> JSONResponse:
    """List preset tasks from input/."""
    presets = []
    for child in sorted(INPUT_ROOT.iterdir()):
        if not child.is_dir():
            continue
        meta = {
            "name": child.name,
            "title": _preset_title(child.name),
            "has_features": (child / "features.md").exists(),
        }
        presets.append(meta)
    return JSONResponse(presets)


def _preset_title(name: str) -> str:
    titles = {
        "task_a": "A — Веб-калькулятор (простое)",
        "task_b": "B — Таск-трекер (среднее)",
        "task_c": "C — Конвертер валют (сложное)",
    }
    return titles.get(name, name)


@app.get("/api/preset/{name}")
async def get_preset(name: str) -> JSONResponse:
    folder = INPUT_ROOT / name
    if not folder.exists() or not folder.is_dir():
        raise HTTPException(status_code=404, detail=f"Preset '{name}' not found")
    bt = (folder / "business_requirements.md").read_text(encoding="utf-8")
    bp = (folder / "business_process.md").read_text(encoding="utf-8")
    feats_path = folder / "features.md"
    feats = feats_path.read_text(encoding="utf-8") if feats_path.exists() else ""
    return JSONResponse({
        "name": name,
        "title": _preset_title(name),
        "business_requirements": bt,
        "business_process": bp,
        "features": feats,
    })


@app.post("/api/jobs")
async def create_job(req: GenerateRequest) -> JSONResponse:
    job_id = uuid.uuid4().hex[:12]
    output_dir = JOBS_ROOT / job_id
    output_dir.mkdir(parents=True, exist_ok=True)

    job = Job(id=job_id, output_dir=output_dir, loop=asyncio.get_running_loop())
    JOBS[job_id] = job

    # Prepare a temp input dir with the user-provided artifacts.
    # Folder name = task name shown in UI meta line.
    input_dir = output_dir / "user_task"
    input_dir.mkdir(parents=True, exist_ok=True)
    write_text(input_dir / "business_requirements.md", req.business_requirements)
    write_text(input_dir / "business_process.md", req.business_process)
    if req.features:
        write_text(input_dir / "features.md", req.features)

    cfg = Config.load()
    overrides: dict[str, str] = {}
    if req.model_fast:
        overrides["fast"] = req.model_fast
    if req.model_smart:
        overrides["smart"] = req.model_smart
    if req.per_step_models:
        # per-step has highest priority
        for step, model in req.per_step_models.items():
            if step and model:
                overrides[step] = model

    threading.Thread(
        target=_run_job_thread,
        args=(job, cfg, input_dir, output_dir, req.skip_use_cases, req.skip_tests,
              overrides, req.self_check),
        daemon=True,
    ).start()

    return JSONResponse({"id": job_id})


@app.post("/api/jobs/{job_id}/refine")
async def refine_job(job_id: str, req: RefineRequest) -> JSONResponse:
    """Apply a refinement comment to an already-completed job.

    Reads the job's artifacts/, runs the refine step, writes patched files back,
    and emits a fresh stream of events on the SAME queue (so the UI re-attaches
    to /stream and sees the new pipeline run).
    """
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    if job.status not in ("done", "error"):
        raise HTTPException(status_code=409, detail="job is still running")

    artifacts_dir = job.output_dir / "artifacts"
    if not artifacts_dir.exists():
        raise HTTPException(status_code=404, detail="no artifacts to refine")

    cfg = Config.load()
    overrides: dict[str, str] = {}
    if req.model_smart:
        overrides["smart"] = req.model_smart

    # Reset the job state for a fresh stream
    job.status = "running"
    job.events = []
    # Re-create queue so previous SSE consumers don't get stale data
    job.queue = asyncio.Queue()

    threading.Thread(
        target=_run_refine_thread,
        args=(job, cfg, artifacts_dir, req.comment, overrides),
        daemon=True,
    ).start()

    return JSONResponse({"id": job_id, "mode": "refine"})


def _run_refine_thread(
    job: Job,
    cfg: Config,
    artifacts_dir: Path,
    comment: str,
    model_overrides: dict[str, str],
) -> None:
    def push(payload: dict[str, Any]) -> None:
        job.events.append(payload)
        if job.loop and not job.loop.is_closed():
            asyncio.run_coroutine_threadsafe(job.queue.put(payload), job.loop)

    try:
        run_refinement(
            cfg=cfg,
            output_dir=artifacts_dir,
            comment=comment,
            on_event=push,
            model_overrides=model_overrides or None,
        )
        job.status = "done"
    except Exception as e:
        log.exception("Refinement %s failed", job.id)
        job.status = "error"
        job.error = str(e)
        push({"type": "error", "error": str(e)})
    finally:
        _save_job_meta(job)
        if job.loop and not job.loop.is_closed():
            asyncio.run_coroutine_threadsafe(job.queue.put(None), job.loop)


def _run_job_thread(
    job: Job,
    cfg: Config,
    input_dir: Path,
    output_dir: Path,
    skip_use_cases: bool,
    skip_tests: bool,
    model_overrides: Optional[dict[str, str]] = None,
    self_check: bool = True,
) -> None:
    """Run pipeline in a background thread, push events into the job's queue."""
    job.status = "running"

    def push(payload: dict[str, Any]) -> None:
        job.events.append(payload)
        # Cross-thread put: schedule on the loop
        if job.loop and not job.loop.is_closed():
            asyncio.run_coroutine_threadsafe(job.queue.put(payload), job.loop)

    try:
        run_pipeline(
            cfg=cfg,
            input_dir=input_dir,
            # output_dir was already created by us; pipeline will clean_output it.
            # We want artifacts directly in our job dir, but clean_output will wipe it.
            # So pass a subdir, then move/keep the input folder elsewhere.
            output_dir=output_dir / "artifacts",
            skip_use_cases=skip_use_cases,
            skip_tests=skip_tests,
            on_event=push,
            model_overrides=model_overrides or None,
            self_check=self_check,
        )
        job.status = "done"
    except Exception as e:
        log.exception("Job %s failed", job.id)
        job.status = "error"
        job.error = str(e)
        push({"type": "error", "error": str(e)})
    finally:
        _save_job_meta(job)
        # Sentinel — tell SSE consumers no more events
        if job.loop and not job.loop.is_closed():
            asyncio.run_coroutine_threadsafe(job.queue.put(None), job.loop)


@app.get("/api/jobs")
async def list_jobs() -> JSONResponse:
    """Return up to 50 most recent jobs from disk + memory, newest first."""
    items = []
    for jid, job in JOBS.items():
        # Try to derive a useful task name from the events (start event has task)
        task_name = job.id
        completed_at = None
        files_count = 0
        for ev in (job.events or []):
            if ev.get("type") == "start" and ev.get("task"):
                task_name = ev["task"]
            if ev.get("type") == "done":
                files_count = ev.get("files", 0)
        # Fallback: use directory mtime
        try:
            mtime = job.output_dir.stat().st_mtime
        except OSError:
            mtime = 0
        items.append({
            "id": jid,
            "status": job.status,
            "task": task_name,
            "files_count": files_count,
            "mtime": mtime,
        })
    items.sort(key=lambda x: x["mtime"], reverse=True)
    return JSONResponse(items[:50])


@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: str) -> JSONResponse:
    """Remove a job and its artifacts from disk."""
    job = JOBS.pop(job_id, None)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    try:
        if job.output_dir.exists():
            shutil.rmtree(job.output_dir)
    except OSError as e:
        log.warning("Failed to remove job dir: %s", e)
    return JSONResponse({"removed": job_id})


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str) -> JSONResponse:
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return JSONResponse(job.to_dict())


@app.get("/api/jobs/{job_id}/stream")
async def stream_job(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")

    async def event_gen():
        # Replay events that already happened (in case client connected late)
        for ev in list(job.events):
            yield {"event": ev.get("type", "message"), "data": json.dumps(ev)}
        # Stream future events
        while True:
            ev = await job.queue.get()
            if ev is None:
                # Sentinel — pipeline ended
                yield {"event": "stream_end", "data": json.dumps({"status": job.status})}
                break
            yield {"event": ev.get("type", "message"), "data": json.dumps(ev)}

    return EventSourceResponse(event_gen())


@app.get("/api/jobs/{job_id}/files")
async def list_files(job_id: str) -> JSONResponse:
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    artifacts_dir = job.output_dir / "artifacts"
    if not artifacts_dir.exists():
        return JSONResponse({"files": []})
    files: list[dict[str, Any]] = []
    for p in sorted(artifacts_dir.rglob("*")):
        if p.is_file():
            rel = p.relative_to(artifacts_dir).as_posix()
            files.append({"path": rel, "size": p.stat().st_size})
    return JSONResponse({"files": files})


@app.get("/api/jobs/{job_id}/file", response_class=PlainTextResponse)
async def get_file(job_id: str, path: str = Query(...)):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    artifacts_dir = job.output_dir / "artifacts"
    target = (artifacts_dir / path).resolve()
    if not str(target).startswith(str(artifacts_dir.resolve())):
        raise HTTPException(status_code=400, detail="bad path")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="file not found")
    return PlainTextResponse(target.read_text(encoding="utf-8", errors="replace"))


@app.get("/api/jobs/{job_id}/app/{path:path}")
async def serve_app_file(job_id: str, path: str):
    """Serve a single file from the generated app's src/ for the live iframe.

    Returns the file with the right content-type so the browser can render
    HTML, fetch CSS/JS as ESM modules, etc.
    """
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    artifacts_dir = job.output_dir / "artifacts"
    if not artifacts_dir.exists():
        raise HTTPException(status_code=404, detail="no artifacts yet")

    # Default to index.html if user hits /app/
    if not path or path.endswith("/"):
        path = (path or "") + "src/index.html"
    target = (artifacts_dir / path).resolve()
    if not str(target).startswith(str(artifacts_dir.resolve())):
        raise HTTPException(status_code=400, detail="bad path")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail=f"file not found: {path}")
    # Use FileResponse — auto sets content-type by extension
    return FileResponse(str(target))


@app.get("/api/jobs/{job_id}/traceability")
async def get_traceability(job_id: str) -> JSONResponse:
    """Build a БТ → UC → ФТ → @implements traceability matrix for the UI."""
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    artifacts_dir = job.output_dir / "artifacts"
    input_dir = job.output_dir / "user_task"
    if not artifacts_dir.exists():
        raise HTTPException(status_code=404, detail="no artifacts")

    # Lazy-import to avoid circular issues at top
    from generator.validators import (
        extract_bt_ids, extract_fr_ids, extract_implements,
        extract_required_bt, extract_uc_ids,
    )

    def _read(p: Path) -> str:
        return p.read_text(encoding="utf-8") if p.exists() else ""

    bt_md = _read(input_dir / "business_requirements.md")
    uc_md = _read(artifacts_dir / "docs" / "use-cases.md")
    fr_md = _read(artifacts_dir / "docs" / "functional-req.md")

    code_files: dict[str, str] = {}
    src = artifacts_dir / "src"
    if src.exists():
        for p in src.rglob("*"):
            if p.is_file():
                rel = "src/" + p.relative_to(src).as_posix()
                code_files[rel] = p.read_text(encoding="utf-8", errors="replace")

    required_bt = sorted(extract_required_bt(bt_md), key=_sort_id_key)
    all_bt = sorted(extract_bt_ids(bt_md), key=_sort_id_key)
    uc_ids = sorted(extract_uc_ids(uc_md), key=_sort_id_key)
    fr_ids = sorted(extract_fr_ids(fr_md), key=_sort_id_key)
    implemented = extract_implements(code_files)

    # For each БТ — which UCs/ФТs reference it?
    bt_to_uc: dict[str, list[str]] = {bt: [] for bt in all_bt}
    bt_to_fr: dict[str, list[str]] = {bt: [] for bt in all_bt}

    # Parse UC blocks
    for uc_id in uc_ids:
        # Find the block "### UC-XX:" up to next "### UC-" (or end)
        pattern = rf"### {re.escape(uc_id)}:.*?(?=### UC-|\Z)"
        match = re.search(pattern, uc_md, re.DOTALL)
        if not match:
            continue
        block = match.group(0)
        for bt in extract_bt_ids(block):
            if bt in bt_to_uc:
                bt_to_uc[bt].append(uc_id)

    for fr_id in fr_ids:
        pattern = rf"### {re.escape(fr_id)}:.*?(?=### ФТ-|\Z)"
        match = re.search(pattern, fr_md, re.DOTALL)
        if not match:
            continue
        block = match.group(0)
        for bt in extract_bt_ids(block):
            if bt in bt_to_fr:
                bt_to_fr[bt].append(fr_id)

    # For each ФТ — which files implement it?
    fr_to_files: dict[str, list[str]] = {fr: [] for fr in fr_ids}
    for path, content in code_files.items():
        for fr in extract_fr_ids("ФТ-" + " ФТ-".join(
            m.group(1) for m in re.finditer(r"@implements\s+ФТ[-‑]?(\d{1,3})", content)
        )):
            if fr in fr_to_files:
                fr_to_files[fr].append(path)

    rows = []
    for bt in all_bt:
        rows.append({
            "bt": bt,
            "required": bt in required_bt,
            "ucs": sorted(set(bt_to_uc.get(bt, [])), key=_sort_id_key),
            "frs": sorted(set(bt_to_fr.get(bt, [])), key=_sort_id_key),
        })

    fr_rows = []
    for fr in fr_ids:
        fr_rows.append({
            "fr": fr,
            "implemented": fr in implemented,
            "files": sorted(set(fr_to_files.get(fr, []))),
        })

    return JSONResponse({
        "bt_rows": rows,
        "fr_rows": fr_rows,
        "totals": {
            "bt_total": len(all_bt),
            "bt_required": len(required_bt),
            "uc_total": len(uc_ids),
            "fr_total": len(fr_ids),
            "fr_implemented": len([fr for fr in fr_ids if fr in implemented]),
        },
    })


def _sort_id_key(s: str) -> tuple[str, int]:
    parts = s.split("-", 1)
    if len(parts) == 2 and parts[1].isdigit():
        return (parts[0], int(parts[1]))
    return (s, 0)


@app.get("/api/jobs/{job_id}/zip")
async def download_zip(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    artifacts_dir = job.output_dir / "artifacts"
    if not artifacts_dir.exists():
        raise HTTPException(status_code=404, detail="no artifacts yet")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in artifacts_dir.rglob("*"):
            if p.is_file():
                zf.write(p, arcname=p.relative_to(artifacts_dir).as_posix())
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="generation_{job_id}.zip"'},
    )


@app.get("/api/health")
async def health() -> JSONResponse:
    cfg = Config.load()
    return JSONResponse({
        "status": "ok",
        "provider": cfg.provider,
        "model_fast": cfg.model_fast,
        "model_smart": cfg.model_smart,
    })


@app.get("/api/models")
async def list_models() -> JSONResponse:
    cfg = Config.load()
    return JSONResponse({
        "provider": cfg.provider,
        "default_fast": cfg.model_fast,
        "default_smart": cfg.model_smart,
        "models": models_for_provider(cfg.provider),
    })

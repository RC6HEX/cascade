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

from generator.config import Config
from generator.io_utils import TaskInput, clean_output, write_text
from generator.pipeline import run_pipeline

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


# ---------- request/response models ----------

class GenerateRequest(BaseModel):
    business_requirements: str = Field(min_length=10)
    business_process: str = Field(min_length=10)
    features: Optional[str] = None
    skip_use_cases: bool = False
    skip_tests: bool = False


# ---------- app ----------

app = FastAPI(title="Autonomous Generator UI", version="0.1.0")


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
    threading.Thread(
        target=_run_job_thread,
        args=(job, cfg, input_dir, output_dir, req.skip_use_cases, req.skip_tests),
        daemon=True,
    ).start()

    return JSONResponse({"id": job_id})


def _run_job_thread(
    job: Job,
    cfg: Config,
    input_dir: Path,
    output_dir: Path,
    skip_use_cases: bool,
    skip_tests: bool,
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
        )
        job.status = "done"
    except Exception as e:
        log.exception("Job %s failed", job.id)
        job.status = "error"
        job.error = str(e)
        push({"type": "error", "error": str(e)})
    finally:
        # Sentinel — tell SSE consumers no more events
        if job.loop and not job.loop.is_closed():
            asyncio.run_coroutine_threadsafe(job.queue.put(None), job.loop)


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

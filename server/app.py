"""FastAPI app: accept clips, run the pipeline, stream progress, serve outputs.

Fully local, single-user, in-memory. Endpoints live under /api and /events so the
Vite dev proxy and the prod static mount use identical relative URLs (no CORS).
"""

from __future__ import annotations

import asyncio
import io
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from clipforge.captions.presets import available_presets, get_preset
from clipforge.config import Config, JobRequest
from clipforge.errors import ClipForgeError, MissingDependencyError
from clipforge.parsing import ClipParseError, parse_clips
from clipforge.tools import resolve_tools
from server.jobs import JobStore
from server.sse import stream_run

_store: JobStore | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _store
    _store = JobStore(asyncio.get_running_loop())
    yield


app = FastAPI(title="ClipForge", lifespan=lifespan)


def store() -> JobStore:
    assert _store is not None
    return _store


# ---- API ---------------------------------------------------------------

@app.get("/api/health")
def health():
    info = {"ffmpeg": False, "ffprobe": False, "yt_dlp": False, "whisper": False}
    try:
        resolve_tools()
        info["ffmpeg"] = info["ffprobe"] = info["yt_dlp"] = True
    except MissingDependencyError:
        pass
    try:
        import faster_whisper  # noqa: F401

        info["whisper"] = True
    except Exception:
        pass
    info["ok"] = all(v for k, v in info.items() if k != "ok")
    return info


@app.get("/api/presets")
def presets():
    out = []
    for name in available_presets():
        p = get_preset(name)
        out.append({"id": name, "label": name.replace("_", " ").title(),
                    "font": p.font_family, "animation": p.animation.value})
    return out


@app.post("/api/runs", status_code=201)
def create_run(req: JobRequest):
    try:
        clips = parse_clips(req.clips)
    except ClipParseError as e:
        raise HTTPException(status_code=422, detail={"errors": e.errors})
    if not clips:
        raise HTTPException(status_code=422, detail={"errors": ["no clips provided"]})
    try:
        run = store().create_run(clips, req.config)
    except ClipForgeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return {"runId": run.run_id, "jobs": [{"jobId": c.id, "clipId": c.id} for c in clips]}


@app.get("/api/runs/{run_id}")
def run_snapshot(run_id: str):
    run = store().get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="unknown run")
    return run.snapshot()


@app.get("/events/{run_id}")
async def events(run_id: str):
    run = store().get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="unknown run")
    return StreamingResponse(
        stream_run(run),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@app.get("/api/runs/{run_id}/clips/{clip_id}/file")
def clip_file(run_id: str, clip_id: str):
    p = store().output_path(run_id, clip_id)
    if not p:
        raise HTTPException(status_code=404, detail="output not ready")
    return FileResponse(str(p), media_type="video/mp4", filename=p.name)


@app.get("/api/runs/{run_id}/zip")
def run_zip(run_id: str):
    run = store().get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="unknown run")
    files: list[Path] = []
    for cid in run.order:
        p = store().output_path(run_id, cid)
        if p:
            files.append(p)
    if not files:
        raise HTTPException(status_code=404, detail="no finished clips")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in files:
            zf.write(str(p), arcname=p.name)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="clipforge-{run_id[:8]}.zip"'},
    )


# ---- static frontend (prod) -------------------------------------------
# Mounted last so /api and /events take precedence. Present only after a build.
_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"
if _DIST.exists():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="spa")

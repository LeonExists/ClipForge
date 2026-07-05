"""In-memory run/job store + bounded worker pool + thread->loop progress bridge.

A *run* is one submission of N clips; each clip is a *job*. yt-dlp/ffmpeg run as
child processes and ct2 releases the GIL, so a bounded ThreadPoolExecutor gives true
parallelism while capping concurrency. Progress callbacks fire on worker threads and
hop to the asyncio loop via call_soon_threadsafe before touching subscriber queues.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from clipforge.batch import BatchRunner
from clipforge.config import Config
from clipforge.deps import preflight
from clipforge.models import Clip, ProgressEvent, Stage
from clipforge.pipeline import ClipProcessor
from clipforge.runner import Runner
from clipforge.transcribe.factory import get_transcriber

# Stage ordering for monotonic progress + overall percentage.
_STAGE_INDEX = {
    Stage.DOWNLOAD: 0,
    Stage.TRANSCRIBE: 1,
    Stage.CAPTION: 2,
    Stage.RENDER: 3,
    Stage.DONE: 4,
    Stage.ERROR: 4,
}
_N_STAGES = 4


@dataclass
class ClipState:
    clip_id: str
    title: str
    stage: str = Stage.DOWNLOAD.value
    pct: float = 0.0
    message: str = ""
    status: str = "pending"  # pending | running | done | error
    output_name: Optional[str] = None
    error: Optional[str] = None
    ts: float = 0.0

    def snapshot(self, run_id: str) -> dict:
        return {
            "runId": run_id,
            "clipId": self.clip_id,
            "jobId": self.clip_id,
            "title": self.title,
            "stage": self.stage,
            "pct": round(self.pct, 1),
            "status": self.status,
            "message": self.message,
            "error": self.error,
            "ts": self.ts,
        }


@dataclass
class Run:
    run_id: str
    config: Config
    clips: dict[str, ClipState]
    order: list[str]
    created_at: float
    subscribers: set = field(default_factory=set)  # set[asyncio.Queue]

    def aggregate(self) -> str:
        statuses = {c.status for c in self.clips.values()}
        if statuses <= {"done"}:
            return "done"
        if "running" in statuses or "pending" in statuses:
            return "running"
        return "partial" if "done" in statuses else "error"

    def snapshot(self) -> dict:
        return {
            "runId": self.run_id,
            "status": self.aggregate(),
            "jobs": [self.clips[cid].snapshot(self.run_id) for cid in self.order],
        }


class JobStore:
    def __init__(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop
        self.runs: dict[str, Run] = {}
        self._tools = None
        self._executors: dict[str, "ThreadPoolExecutor"] = {}

    def _ensure_tools(self):
        if self._tools is None:
            self._tools = preflight()
        return self._tools

    def create_run(self, clips: list[Clip], config: Config) -> Run:
        from concurrent.futures import ThreadPoolExecutor

        run_id = uuid.uuid4().hex
        states = {c.id: ClipState(c.id, c.title) for c in clips}
        run = Run(run_id, config, states, [c.id for c in clips], time.time())
        self.runs[run_id] = run

        tools = self._ensure_tools()
        runner = Runner(tools)
        transcriber = get_transcriber(config)
        processor = ClipProcessor(runner, transcriber, config)

        pool = ThreadPoolExecutor(max_workers=config.max_concurrency)
        self._executors[run_id] = pool

        def on_progress(ev: ProgressEvent) -> None:
            # Worker thread -> hop to the loop before mutating state / fanning out.
            self.loop.call_soon_threadsafe(self._apply, run, ev)

        batch = BatchRunner(processor, submit=pool.submit)

        # Kick the whole batch off on a background thread so create_run returns fast.
        def _drive():
            try:
                batch.run(clips, on_progress)
            finally:
                self.loop.call_soon_threadsafe(self._finalize, run)

        pool.submit(_drive)
        return run

    def _apply(self, run: Run, ev: ProgressEvent) -> None:
        cs = run.clips.get(ev.clip_id)
        if cs is None:
            return
        now = time.time()
        cs.stage = ev.stage.value
        cs.status = ev.status
        cs.message = ev.message
        cs.ts = now
        # Overall percentage across the 4 working stages.
        idx = _STAGE_INDEX.get(ev.stage, 0)
        if ev.status == "done":
            cs.pct = 100.0
        elif ev.status == "error":
            cs.error = ev.message
        else:
            cs.pct = min(100.0, (idx + (ev.pct / 100.0)) / _N_STAGES * 100.0)
        for q in list(run.subscribers):
            q.put_nowait(cs.snapshot(run.run_id))

    def _finalize(self, run: Run) -> None:
        # Send a terminal marker to all subscribers.
        for q in list(run.subscribers):
            q.put_nowait({"event": "end", "runId": run.run_id, "status": run.aggregate()})

    def get(self, run_id: str) -> Optional[Run]:
        return self.runs.get(run_id)

    def output_path(self, run_id: str, clip_id: str) -> Optional[Path]:
        run = self.runs.get(run_id)
        if not run:
            return None
        cs = run.clips.get(clip_id)
        if not cs or cs.status != "done":
            return None
        from clipforge.naming import output_name

        # Reconstruct the output path deterministically from title+id.
        name = output_name(cs.title, cs.clip_id)
        p = Path(run.config.output_dir) / name
        return p if p.exists() else None

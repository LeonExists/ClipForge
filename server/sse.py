"""SSE fan-out for per-run progress streaming."""

from __future__ import annotations

import asyncio
import json

from server.jobs import Run


def _pack(obj: dict, event: str | None = None) -> str:
    prefix = f"event: {event}\n" if event else ""
    return f"{prefix}data: {json.dumps(obj)}\n\n"


async def stream_run(run: Run):
    """Yield an SSE stream: snapshot-on-connect, live events, heartbeat, terminal.

    A late subscriber gets the current state immediately (snapshot), so it renders
    correctly even if it connects mid-run.
    """
    q: asyncio.Queue = asyncio.Queue()
    run.subscribers.add(q)
    try:
        # 1. snapshot of current state
        for cid in run.order:
            yield _pack(run.clips[cid].snapshot(run.run_id), event="progress")

        # 2. if the run is already terminal, close immediately
        if run.aggregate() in ("done", "partial", "error") and _all_terminal(run):
            yield _pack({"event": "end", "runId": run.run_id, "status": run.aggregate()}, event="end")
            return

        # 3. live events with heartbeat
        while True:
            try:
                item = await asyncio.wait_for(q.get(), timeout=15)
            except asyncio.TimeoutError:
                yield ": ping\n\n"  # keep-alive comment
                continue
            if item.get("event") == "end":
                yield _pack(item, event="end")
                return
            yield _pack(item, event="progress")
    finally:
        run.subscribers.discard(q)


def _all_terminal(run: Run) -> bool:
    return all(c.status in ("done", "error") for c in run.clips.values())

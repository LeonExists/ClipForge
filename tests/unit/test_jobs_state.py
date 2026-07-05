"""Job aggregate-state transitions. Pure logic on the Run dataclass."""

import time

from clipforge.config import Config
from server.jobs import ClipState, Run


def _run(*statuses):
    clips = {}
    order = []
    for i, s in enumerate(statuses):
        cid = f"c{i}"
        cs = ClipState(cid, f"title {i}")
        cs.status = s
        clips[cid] = cs
        order.append(cid)
    return Run("run1", Config(), clips, order, time.time())


def test_all_done():
    assert _run("done", "done").aggregate() == "done"


def test_running_when_any_pending_or_running():
    assert _run("done", "running").aggregate() == "running"
    assert _run("pending", "done").aggregate() == "running"


def test_partial_when_done_and_error():
    assert _run("done", "error").aggregate() == "partial"


def test_all_error():
    assert _run("error", "error").aggregate() == "error"


def test_snapshot_shape():
    run = _run("done", "running")
    snap = run.snapshot()
    assert snap["runId"] == "run1"
    assert snap["status"] == "running"
    assert len(snap["jobs"]) == 2
    job = snap["jobs"][0]
    assert set(job) >= {"runId", "clipId", "jobId", "stage", "pct", "status"}


def test_clip_snapshot_fields():
    cs = ClipState("cid", "My Title")
    cs.stage = "render"
    cs.pct = 42.4
    cs.status = "running"
    snap = cs.snapshot("run1")
    assert snap["clipId"] == "cid"
    assert snap["stage"] == "render"
    assert snap["pct"] == 42.4
    assert snap["status"] == "running"

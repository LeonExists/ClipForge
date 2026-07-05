"""Batch orchestration ABOVE the per-clip processor.

Owns videoId grouping and the shared-source dedupe: a covering plan is downloaded
ONCE and sliced per clip, so a shared videoId is never fetched in full more than
needed. Runs clips through a supplied executor (bounded pool) or serially.
"""

from __future__ import annotations

from concurrent.futures import Future
from typing import Callable, Optional

from clipforge.config import Config
from clipforge.download.plan import DownloadMode, DownloadPlan, plan_downloads
from clipforge.models import Clip, ClipResult, ProgressCallback, ProgressEvent, Stage
from clipforge.pipeline import ClipProcessor

# submit(fn) -> Future, or None for serial execution.
SubmitFn = Callable[[Callable[[], ClipResult]], "Future[ClipResult]"]


class BatchRunner:
    def __init__(self, processor: ClipProcessor, submit: Optional[SubmitFn] = None):
        self.processor = processor
        self.submit = submit

    def run(self, clips: list[Clip], on_progress: ProgressCallback) -> list[ClipResult]:
        """Process all clips. If a submit fn was supplied, dispatch concurrently."""
        plans = plan_downloads(clips, self.processor.cfg)

        if self.submit is None:
            return self._run_serial(plans, on_progress)
        return self._run_concurrent(plans, on_progress)

    # -- serial (CLI default) -----------------------------------------------

    def _run_serial(self, plans: list[DownloadPlan], on_progress) -> list[ClipResult]:
        results: list[ClipResult] = []
        for plan in plans:
            covering_path = self._prefetch_covering(plan, on_progress)
            for clip in plan.clips:
                results.append(
                    self.processor.process(
                        clip, on_progress, plan=plan, covering_path=covering_path
                    )
                )
        return results

    # -- concurrent (web / bounded pool) ------------------------------------

    def _run_concurrent(self, plans: list[DownloadPlan], on_progress) -> list[ClipResult]:
        futures: list[Future[ClipResult]] = []
        for plan in plans:
            covering_path = self._prefetch_covering(plan, on_progress)
            for clip in plan.clips:
                futures.append(
                    self.submit(  # type: ignore[misc]
                        lambda c=clip, p=plan, cp=covering_path: self.processor.process(
                            c, on_progress, plan=p, covering_path=cp
                        )
                    )
                )
        return [f.result() for f in futures]

    def _prefetch_covering(self, plan: DownloadPlan, on_progress) -> Optional[str]:
        if plan.mode != DownloadMode.COVERING:
            return None
        cid = plan.clips[0].id

        def cover_progress(frac: float, status: str) -> None:
            on_progress(ProgressEvent(cid, Stage.DOWNLOAD, frac * 100.0, f"shared source: {status}"))

        return self.processor.downloader.fetch_covering(plan, cover_progress)

"""Execute download plans via yt-dlp / ffmpeg (through the Runner seam).

Orchestrates: metadata duration probe (+ clamp), ranged fetch or covering
download + local slice, progress streaming, and typed error classification. All
subprocess work routes through Runner; argv is built by the pure builders in args.py.
"""

from __future__ import annotations

import glob
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from clipforge.config import Config
from clipforge.download import args as ytargs
from clipforge.download.plan import DownloadMode, DownloadPlan
from clipforge.download.progress import parse_progress
from clipforge.errors import (
    DownloadError,
    GenericDownloadError,
    NoVideoStreamError,
    classify_ytdlp_error,
)
from clipforge.ffmpeg import probe_has_video_stream
from clipforge.models import Clip
from clipforge.runner import Runner

# Callback: fraction 0..1, human message.
ProgressFn = Callable[[float, str], None]


@dataclass(frozen=True)
class SegmentResult:
    clip_id: str
    path: str          # cut mp4; starts at t=0
    duration: float
    mode: DownloadMode
    keyframe_accurate: bool


class SegmentDownloader:
    """Runs download plans, producing one cut segment file per clip."""

    def __init__(self, runner: Runner, cfg: Config, work_dir: str | Path):
        self.runner = runner
        self.cfg = cfg
        self.work_dir = str(work_dir)
        os.makedirs(self.work_dir, exist_ok=True)

    # -- metadata ------------------------------------------------------------

    def probe_duration(self, url: str) -> Optional[float]:
        res = self.runner.ytdlp(ytargs.build_metadata_argv(url))
        if not res.ok:
            return None
        line = (res.stdout or "").strip().splitlines()
        if not line:
            return None
        try:
            return float(line[0])
        except ValueError:
            return None

    # -- covering source (shared across a videoId group) ---------------------

    def fetch_covering(self, plan: DownloadPlan, on_progress: ProgressFn) -> str:
        """Download the covering span once; return its on-disk path."""
        out_tmpl = os.path.join(self.work_dir, f"{plan.videoId}__cover.%(ext)s")
        url = plan.clips[0].url
        argv = ytargs.build_ytdlp_argv(url, plan.cover_start, plan.cover_end, out_tmpl, self.cfg)
        self._run_ytdlp(argv, url, on_progress)
        path = self._resolve_output(os.path.join(self.work_dir, f"{plan.videoId}__cover.*"))
        self._assert_has_video(path, url)
        return path

    # -- per-clip ------------------------------------------------------------

    def fetch_ranged(self, clip: Clip, on_progress: ProgressFn) -> SegmentResult:
        """Download only [clip.start, clip.end] for a single clip."""
        start, end = self._clamped_range(clip)
        out_tmpl = ytargs.default_out_template(self.work_dir, clip.videoId, start, end)
        argv = ytargs.build_ytdlp_argv(clip.url, start, end, out_tmpl, self.cfg)
        self._run_ytdlp(argv, clip.url, on_progress)
        glob_pat = ytargs.default_out_template(self.work_dir, clip.videoId, start, end).replace(
            ".%(ext)s", ".*"
        )
        path = self._resolve_output(glob_pat)
        self._assert_has_video(path, clip.url)
        return SegmentResult(clip.id, path, end - start, DownloadMode.RANGED, self.cfg.precise_cuts)

    def slice_from_covering(self, covering_path: str, plan: DownloadPlan, clip: Clip,
                            encoder: str | None = None) -> SegmentResult:
        """Slice a single clip out of an already-downloaded covering file."""
        rel_start = clip.start - plan.cover_start
        dst = os.path.join(self.work_dir, f"{clip.videoId}__{clip.id}.mp4")
        argv = ytargs.build_slice_argv(
            covering_path, dst, rel_start, clip.duration, self.cfg, encoder
        )
        res = self.runner.ffmpeg(argv)
        if not res.ok:
            raise GenericDownloadError(url=clip.url, raw=res.stderr[-800:])
        return SegmentResult(clip.id, dst, clip.duration, DownloadMode.COVERING, self.cfg.precise_cuts)

    # -- helpers -------------------------------------------------------------

    def _clamped_range(self, clip: Clip) -> tuple[float, float]:
        start, end = clip.start, clip.end
        if self.cfg.clamp_end_to_duration:
            dur = self.probe_duration(clip.url)
            if dur is not None and end > dur:
                end = dur
        return start, end

    def _run_ytdlp(self, argv: list[str], url: str, on_progress: ProgressFn) -> None:
        def on_line(line: str) -> None:
            p = parse_progress(line)
            if p is not None and p.fraction is not None:
                on_progress(p.fraction, p.status)

        res = self.runner.ytdlp_streaming(argv, on_line)
        if not res.ok:
            raise classify_ytdlp_error(res.stderr, url)

    def _assert_has_video(self, path: str, url: str) -> None:
        """Fail fast (typed, at DOWNLOAD) if the fetched file has no video track.

        Guards against yt-dlp's ffmpeg downloader emitting an audio-only merge from
        a source it couldn't seek — otherwise this only surfaces as a cryptic
        'no video stream' at the much-later render probe.
        """
        if not probe_has_video_stream(self.runner, path):
            raise NoVideoStreamError(url=url, raw=f"audio-only output: {path}")

    def _resolve_output(self, glob_pattern: str) -> str:
        matches = sorted(glob.glob(glob_pattern))
        # Prefer the merged .mp4 if several intermediate files exist.
        mp4s = [m for m in matches if m.lower().endswith(".mp4")]
        chosen = mp4s or matches
        if not chosen:
            raise GenericDownloadError(raw=f"no output file matched {glob_pattern!r}")
        return chosen[0]

"""Execute download plans via yt-dlp / ffmpeg (through the Runner seam).

Orchestrates: metadata duration probe (+ clamp), ranged fetch or covering
download + local slice, progress streaming, and typed error classification. All
subprocess work routes through Runner; argv is built by the pure builders in args.py.
"""

from __future__ import annotations

import glob
import os
import threading
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
        # Cache of whole-video native downloads (fallback path), keyed by videoId,
        # so multiple clips from one video pull the source at most once. Guarded by
        # a per-instance lock for the concurrent (web pool) executor.
        self._source_paths: dict[str, str] = {}
        self._source_lock = threading.Lock()

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
        """Download the covering span once; return its on-disk path.

        Same HLS-first strategy as fetch_ranged: on a ranged miss, fall back to the
        native full-source download. Since that file starts at t=0 (not at
        cover_start), reset plan.cover_start to 0 so every slice_from_covering in the
        group computes the correct ABSOLUTE offset.
        """
        out_tmpl = os.path.join(self.work_dir, f"{plan.videoId}__cover.%(ext)s")
        url = plan.clips[0].url
        argv = ytargs.build_ytdlp_argv(url, plan.cover_start, plan.cover_end, out_tmpl, self.cfg)
        try:
            self._run_ytdlp(argv, url, on_progress)
            path = self._resolve_output(os.path.join(self.work_dir, f"{plan.videoId}__cover.*"))
            self._assert_has_video(path, url)
            return path
        except (NoVideoStreamError, DownloadError):
            src = self._ensure_source(plan.clips[0], on_progress)
            plan.cover_start = 0.0  # full source starts at t=0 -> slices use absolute start
            return src

    # -- per-clip ------------------------------------------------------------

    def fetch_ranged(self, clip: Clip, on_progress: ProgressFn,
                     encoder: str | None = None) -> SegmentResult:
        """Produce the cut segment for a single clip.

        Fast path: ranged --download-sections against HLS (full-res, seconds). If
        that yields no usable video — YouTube serves HLS only intermittently, and
        the ffmpeg-downloader byte-seek can't range fragmented DASH — fall back to a
        native full download of the source (cached per videoId) sliced locally, so
        quality never silently degrades to progressive 360p.
        """
        start, end = self._clamped_range(clip)
        try:
            path = self._fetch_ranged_sections(clip, start, end, on_progress)
            return SegmentResult(
                clip.id, path, end - start, DownloadMode.RANGED, self.cfg.precise_cuts
            )
        except (NoVideoStreamError, DownloadError):
            # HLS unavailable / ranged seek failed: pull the source natively + slice.
            return self._fetch_via_full_source(clip, start, end, on_progress, encoder)

    def _fetch_ranged_sections(self, clip: Clip, start: float, end: float,
                               on_progress: ProgressFn) -> str:
        out_tmpl = ytargs.default_out_template(self.work_dir, clip.videoId, start, end)
        argv = ytargs.build_ytdlp_argv(clip.url, start, end, out_tmpl, self.cfg)
        self._run_ytdlp(argv, clip.url, on_progress)
        glob_pat = out_tmpl.replace(".%(ext)s", ".*")
        path = self._resolve_output(glob_pat)
        self._assert_has_video(path, clip.url)
        return path

    def _fetch_via_full_source(self, clip: Clip, start: float, end: float,
                               on_progress: ProgressFn,
                               encoder: str | None) -> SegmentResult:
        src = self._ensure_source(clip, on_progress)
        dst = os.path.join(self.work_dir, f"{clip.videoId}__{clip.id}.mp4")
        # The source starts at t=0, so the cut offset is the ABSOLUTE clip start.
        argv = ytargs.build_slice_argv(src, dst, start, end - start, self.cfg, encoder)
        res = self.runner.ffmpeg(argv)
        if not res.ok:
            raise GenericDownloadError(url=clip.url, raw=res.stderr[-800:])
        self._assert_has_video(dst, clip.url)
        return SegmentResult(clip.id, dst, end - start, DownloadMode.RANGED, self.cfg.precise_cuts)

    def _ensure_source(self, clip: Clip, on_progress: ProgressFn) -> str:
        """Download the whole video once (native downloader), cached per videoId."""
        with self._source_lock:
            cached = self._source_paths.get(clip.videoId)
            if cached and os.path.exists(cached):
                return cached
            out_tmpl = ytargs.source_out_template(self.work_dir, clip.videoId)
            argv = ytargs.build_ytdlp_full_argv(clip.url, out_tmpl, self.cfg)

            def full_progress(frac: float, status: str) -> None:
                on_progress(frac, f"full source: {status}")

            self._run_ytdlp(argv, clip.url, full_progress)
            path = self._resolve_output(
                os.path.join(self.work_dir, f"{clip.videoId}__source.*")
            )
            self._assert_has_video(path, clip.url)
            self._source_paths[clip.videoId] = path
            return path

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

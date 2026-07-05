"""Pure argv builders for yt-dlp and the covering-mode ffmpeg slice.

These never touch subprocess — tests assert the constructed argv directly.
"""

from __future__ import annotations

import os

from clipforge.config import Config

# Sentinel-prefixed, tab-separated progress template so we can parse only our own
# progress lines out of yt-dlp's chatter (see download/progress.py).
PROGRESS_TMPL = (
    "download:__CFDL__\t%(progress.status)s\t%(progress.downloaded_bytes)s\t"
    "%(progress.total_bytes)s\t%(progress.total_bytes_estimate)s\t"
    "%(progress.fragment_index)s\t%(progress.fragment_count)s\t"
    "%(progress.eta)s\t%(progress.speed)s"
)


def _fmt_time(t: float) -> str:
    """Format a float second for --download-sections (trim trailing zeros)."""
    return f"{t:.3f}".rstrip("0").rstrip(".")


def build_ytdlp_argv(
    url: str,
    start: float,
    end: float,
    out_template: str,
    cfg: Config,
) -> list[str]:
    """Argv (without the yt-dlp binary prefix) for a ranged segment download.

    Fetches ONLY [start, end] via --download-sections so a short clip from a long
    video downloads in seconds. --force-keyframes-at-cuts is added iff precise_cuts.
    """
    argv = [
        "-f", cfg.download_format,
        "--download-sections", f"*{_fmt_time(start)}-{_fmt_time(end)}",
    ]
    if cfg.precise_cuts:
        argv.append("--force-keyframes-at-cuts")
    argv += [
        "--merge-output-format", "mp4",
        "--no-playlist",
        "--newline",
        "--progress-template", PROGRESS_TMPL,
        "--retries", str(cfg.download_retries),
        "--fragment-retries", "10",
        "--concurrent-fragments", str(cfg.concurrent_fragments),
        "--socket-timeout", str(cfg.socket_timeout_sec),
        "-o", out_template,
        url,
    ]
    return argv


def build_metadata_argv(url: str) -> list[str]:
    """Argv for a metadata-only probe (duration), no media bytes."""
    return ["--skip-download", "--no-warnings", "--print", "%(duration)s", url]


def build_slice_argv(
    src: str,
    dst: str,
    rel_start: float,
    duration: float,
    cfg: Config,
    encoder: str | None = None,
) -> list[str]:
    """Argv (without ffmpeg prefix) to slice a clip out of a covering download.

    -ss/-t are relative to the covering file (which itself starts at t=0). Uses
    stream copy for a fast cut; a frame-accurate re-encode is deferred to the render
    stage which re-encodes anyway.
    """
    argv = ["-y", "-ss", _fmt_time(rel_start), "-i", src, "-t", _fmt_time(duration)]
    if cfg.precise_cuts and encoder:
        argv += ["-c:v", encoder, "-c:a", "aac"]
    else:
        argv += ["-c", "copy"]
    argv.append(dst)
    return argv


def default_out_template(work_dir: str, video_id: str, start: float, end: float) -> str:
    """Deterministic output template for a ranged segment file."""
    fname = f"{video_id}__{_fmt_time(start)}-{_fmt_time(end)}.%(ext)s"
    return os.path.join(work_dir, fname)

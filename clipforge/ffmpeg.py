"""Low-level ffmpeg/ffprobe helpers: path escaping + source probing.

No pipeline logic lives here — just the plumbing shared by reframe/encode.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from clipforge.errors import EncodeError
from clipforge.runner import Runner


@dataclass(frozen=True)
class SourceInfo:
    path: str
    width: int
    height: int
    sar: str = "1:1"
    duration: float | None = None


def escape_filter_path(p: str) -> str:
    r"""Escape a path for use inside an ffmpeg filter argument (e.g. ass=/fontsdir=).

    ffmpeg filter args want forward slashes; the Windows drive colon must be
    backslash-escaped so the parser doesn't read it as an option separator:
        C:\Users\a b\cap.ass  ->  C\:/Users/a b/cap.ass

    Note: for the common case we write captions.ass into the run tmp dir and run
    ffmpeg with cwd=<tmp> using the bare filename, avoiding escaping entirely. This
    helper is used for fontsdir (which points at the packaged assets dir).
    """
    p = p.replace("\\", "/")
    p = re.sub(r"^([A-Za-z]):", r"\1\\:", p)
    return p


def probe_has_video_stream(runner: Runner, path: str | Path) -> bool:
    """True iff `path` contains at least one video stream.

    Cheap guard used at download time: yt-dlp's ffmpeg downloader can stall on a
    non-seekable source and emit an audio-only file, which otherwise only fails
    much later at the render probe. Returns False (never raises) on ffprobe error.
    """
    res = runner.ffprobe([
        "-v", "error",
        "-select_streams", "v",
        "-show_entries", "stream=codec_type",
        "-of", "csv=p=0",
        str(path),
    ])
    return res.ok and "video" in (res.stdout or "")


def ffprobe_dims(runner: Runner, path: str | Path) -> SourceInfo:
    """Probe width/height/sar/duration of a media file via ffprobe -show_streams."""
    path = str(path)
    res = runner.ffprobe([
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,sample_aspect_ratio",
        "-show_entries", "format=duration",
        "-of", "json",
        path,
    ])
    if not res.ok:
        raise EncodeError(f"ffprobe failed for {path}: {res.stderr.strip()}")
    try:
        data = json.loads(res.stdout)
        stream = (data.get("streams") or [{}])[0]
        width = int(stream.get("width") or 0)
        height = int(stream.get("height") or 0)
        sar = stream.get("sample_aspect_ratio") or "1:1"
        if sar in ("0:1", "", None):
            sar = "1:1"
        dur_raw = (data.get("format") or {}).get("duration")
        duration = float(dur_raw) if dur_raw not in (None, "N/A") else None
    except (ValueError, KeyError, IndexError, TypeError) as e:
        raise EncodeError(f"could not parse ffprobe output for {path}: {e}") from e

    if width <= 0 or height <= 0:
        raise EncodeError(f"ffprobe reported no video stream for {path}")
    return SourceInfo(path=path, width=width, height=height, sar=sar, duration=duration)

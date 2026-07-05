"""Locate external binaries (ffmpeg, ffprobe, yt-dlp) with actionable errors.

Detection order for each tool: an explicit env override, then shutil.which. yt-dlp
additionally falls back to `python -m yt_dlp` so it runs from the venv even when not
on PATH.
"""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass

from clipforge.errors import MissingDependencyError


@dataclass(frozen=True)
class ToolPaths:
    ffmpeg: str
    ffprobe: str
    # yt-dlp is a command *prefix* (list) so the `python -m yt_dlp` fallback works.
    ytdlp: tuple[str, ...]


def _which(name: str, env_var: str) -> str | None:
    override = os.environ.get(env_var)
    if override:
        return override
    return shutil.which(name)


def resolve_tools() -> ToolPaths:
    """Resolve all required binaries or raise MissingDependencyError with hints."""
    ff = _which("ffmpeg", "CLIPFORGE_FFMPEG_BIN")
    fp = _which("ffprobe", "CLIPFORGE_FFPROBE_BIN")
    yt = _which("yt-dlp", "CLIPFORGE_YTDLP_BIN")

    missing: list[str] = []
    if ff is None:
        missing.append(
            "ffmpeg not found on PATH. ClipForge needs ffmpeg (>=5.0) to cut/encode. "
            "Install it (e.g. `winget install Gyan.FFmpeg`) and ensure `ffmpeg` is on PATH."
        )
    if fp is None:
        missing.append(
            "ffprobe not found on PATH (ships with ffmpeg). Reinstall ffmpeg so ffprobe is present."
        )

    # yt-dlp: PATH/env binary, else module form from this interpreter.
    if yt is not None:
        ytdlp_cmd: tuple[str, ...] = (yt,)
    else:
        try:
            import yt_dlp  # noqa: F401

            ytdlp_cmd = (sys.executable, "-m", "yt_dlp")
        except Exception:
            ytdlp_cmd = ()
            missing.append(
                "yt-dlp not found. Install with `pip install -U yt-dlp` "
                "or `winget install yt-dlp.yt-dlp`, then restart ClipForge."
            )

    if missing:
        raise MissingDependencyError("\n".join(missing))

    return ToolPaths(ffmpeg=ff, ffprobe=fp, ytdlp=ytdlp_cmd)  # type: ignore[arg-type]

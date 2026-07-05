"""Dependency preflight: fail fast with actionable messages before doing work."""

from __future__ import annotations

from clipforge.errors import MissingDependencyError
from clipforge.tools import ToolPaths, resolve_tools


def preflight() -> ToolPaths:
    """Ensure ffmpeg/ffprobe/yt-dlp are present and faster-whisper is importable.

    Returns the resolved ToolPaths. Raises MissingDependencyError with install
    hints on the first missing piece.
    """
    tools = resolve_tools()  # raises for ffmpeg/ffprobe/yt-dlp

    try:
        import faster_whisper  # noqa: F401
    except Exception as e:  # pragma: no cover - environment-specific
        raise MissingDependencyError(
            "faster-whisper is not importable. Install it with "
            "`pip install faster-whisper` (and a CPU torch build if needed).\n"
            f"Import error: {e}"
        ) from e

    return tools

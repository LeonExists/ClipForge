"""THE subprocess seam — the only module that calls subprocess.

Every other lane builds pure `list[str]` argv and passes it here. Tests monkeypatch
this Runner (or the `run` function) so no shell-out executes in the unit suite.

Always list-args, never shell=True (the project path contains spaces on Windows).
"""

from __future__ import annotations

import collections
import subprocess
import sys
import threading
from dataclasses import dataclass
from typing import Callable, Optional, Sequence

from clipforge.tools import ToolPaths

# On Windows, keep child console windows from flashing up.
_CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


@dataclass(frozen=True)
class CommandResult:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def run(
    argv: Sequence[str],
    *,
    timeout: Optional[float] = None,
    cwd: Optional[str] = None,
    check: bool = False,
) -> CommandResult:
    """Run argv to completion, capturing stdout/stderr. No shell."""
    proc = subprocess.run(
        list(argv),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        cwd=cwd,
        creationflags=_CREATE_NO_WINDOW,
    )
    result = CommandResult(list(argv), proc.returncode, proc.stdout or "", proc.stderr or "")
    if check and not result.ok:
        raise subprocess.CalledProcessError(
            result.returncode, list(argv), result.stdout, result.stderr
        )
    return result


def run_streaming(
    argv: Sequence[str],
    on_line: Callable[[str], None],
    *,
    cwd: Optional[str] = None,
) -> CommandResult:
    """Run argv, streaming stdout lines to `on_line`; drain stderr on a thread.

    stderr is drained concurrently into a ring buffer to avoid the classic
    full-pipe deadlock (select() doesn't work on Windows pipes).
    """
    proc = subprocess.Popen(
        list(argv),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        cwd=cwd,
        creationflags=_CREATE_NO_WINDOW,
    )
    err: collections.deque[str] = collections.deque(maxlen=400)

    def _drain() -> None:
        assert proc.stderr is not None
        for line in proc.stderr:
            err.append(line)

    t = threading.Thread(target=_drain, daemon=True)
    t.start()

    assert proc.stdout is not None
    for line in proc.stdout:
        on_line(line.rstrip("\n"))

    proc.wait()
    t.join(timeout=5)
    return CommandResult(list(argv), proc.returncode, "", "".join(err))


class Runner:
    """Thin wrapper that prepends resolved binaries to per-tool argv."""

    def __init__(self, tools: ToolPaths):
        self.tools = tools

    def ffmpeg(self, args: Sequence[str], **kw) -> CommandResult:
        return run([self.tools.ffmpeg, "-hide_banner", "-nostdin", *args], **kw)

    def ffmpeg_streaming(self, args: Sequence[str], on_line, **kw) -> CommandResult:
        return run_streaming([self.tools.ffmpeg, "-hide_banner", "-nostdin", *args], on_line, **kw)

    def ffprobe(self, args: Sequence[str], **kw) -> CommandResult:
        return run([self.tools.ffprobe, "-hide_banner", *args], **kw)

    def ytdlp(self, args: Sequence[str], **kw) -> CommandResult:
        return run([*self.tools.ytdlp, *args], **kw)

    def ytdlp_streaming(self, args: Sequence[str], on_line, **kw) -> CommandResult:
        return run_streaming([*self.tools.ytdlp, *args], on_line, **kw)

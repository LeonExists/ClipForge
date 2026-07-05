"""Shared test fixtures.

The `fake_runner` fixture is the mock seam for the shell-out layer: it records the
argv it is asked to run and returns a canned CommandResult, so pure argv-building
logic in the download/reframe/encode lanes is tested without executing anything.
"""

from __future__ import annotations

import pathlib

import pytest

from clipforge.runner import CommandResult


@pytest.fixture
def fake_runner():
    """Factory: make(returncode=, stdout=, stderr=[, per_tool=]) -> a FakeRunner.

    The returned runner records (tool_name, argv) tuples in `.calls`. `per_tool`
    maps a tool name to a dict of overrides for that tool's result.
    """

    def make(*, returncode: int = 0, stdout: str = "", stderr: str = "", per_tool: dict | None = None):
        per_tool = per_tool or {}
        calls: list[tuple[str, list[str]]] = []

        class FakeRunner:
            def __init__(self):
                self.calls = calls

            def _rec(self, name: str, args, prefix=()):
                argv = [*prefix, *args]
                calls.append((name, argv))
                over = per_tool.get(name, {})
                return CommandResult(
                    argv,
                    over.get("returncode", returncode),
                    over.get("stdout", stdout),
                    over.get("stderr", stderr),
                )

            def ffmpeg(self, args, **kw):
                return self._rec("ffmpeg", args)

            def ffmpeg_streaming(self, args, on_line, **kw):
                return self._rec("ffmpeg", args)

            def ffprobe(self, args, **kw):
                return self._rec("ffprobe", args)

            def ytdlp(self, args, **kw):
                return self._rec("ytdlp", args)

            def ytdlp_streaming(self, args, on_line, **kw):
                return self._rec("ytdlp", args)

        return FakeRunner()

    return make


@pytest.fixture
def fixtures_dir():
    return pathlib.Path(__file__).parent / "fixtures"

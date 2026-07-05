"""Runtime capability probes: encoder selection + whisper device selection.

The encoder probe ACTUALLY attempts a tiny encode with each candidate and keeps the
first that succeeds — never a static `ffmpeg -encoders` list check. On this box
h264_nvenc/h264_amf are advertised but fail at runtime (no NVIDIA/AMD driver), so
only a real attempt lands correctly on h264_qsv, then libx264.

Selection logic is pure (takes an injected probe_fn) so it is unit-tested without
executing ffmpeg.
"""

from __future__ import annotations

import functools
from typing import Callable

from clipforge.runner import Runner


def build_probe_argv(encoder: str, w: int = 1080, h: int = 1920) -> list[str]:
    """Argv (without ffmpeg prefix) for a tiny real encode that mirrors the real graph.

    The scale+format matches the shape frames reach the encoder in, so a passing
    probe implies a passing encode (e.g. qsv needs nv12 after scaling).
    """
    return [
        "-loglevel", "error",
        "-f", "lavfi",
        "-i", "color=c=black:s=256x256:r=30",
        "-t", "0.1",
        "-vf", f"scale={w}:{h},format=nv12",
        "-c:v", encoder,
        "-f", "null", "-",
    ]


def select_encoder(candidates: list[str], probe_fn: Callable[[str], bool]) -> str:
    """Return the first candidate for which probe_fn(encoder) is True.

    Pure: probe_fn does the actual encode attempt (injected). Falls back to libx264
    if nothing else works (and probe_fn('libx264') should always be True).
    """
    for enc in candidates:
        if probe_fn(enc):
            return enc
    return "libx264"


@functools.lru_cache(maxsize=None)
def _cached_probe(runner_id: int, candidates: tuple[str, ...], w: int, h: int) -> str:
    # runner_id keeps the cache keyed to a specific Runner instance.
    return _uncached_probe(_RUNNERS[runner_id], list(candidates), w, h)


_RUNNERS: dict[int, Runner] = {}


def _uncached_probe(runner: Runner, candidates: list[str], w: int, h: int) -> str:
    def probe_fn(enc: str) -> bool:
        return runner.ffmpeg(build_probe_argv(enc, w, h)).ok

    return select_encoder(candidates, probe_fn)


def probe_encoder(runner: Runner, candidates: list[str], w: int = 1080, h: int = 1920) -> str:
    """Probe encoders via the Runner, caching the winner per (runner, candidates, dims)."""
    _RUNNERS[id(runner)] = runner
    return _cached_probe(id(runner), tuple(candidates), w, h)


def probe_device_compute(device: str = "auto", compute_type: str = "auto") -> tuple[str, str]:
    """Select (device, compute_type) for faster-whisper.

    'auto' probes ctranslate2's CUDA device count (CTranslate2 — not torch — drives
    faster-whisper). CUDA float16 if a device exists, else CPU int8. On this box
    this resolves to ('cpu', 'int8').
    """
    if device != "auto":
        if compute_type != "auto":
            return device, compute_type
        return device, ("float16" if device == "cuda" else "int8")
    try:
        import ctranslate2

        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda", (compute_type if compute_type != "auto" else "float16")
    except Exception:
        pass
    return "cpu", (compute_type if compute_type != "auto" else "int8")

"""Core data types shared across the pipeline. No framework, no I/O."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Optional


class Stage(str, Enum):
    """Pipeline stages, in execution order.

    Note: reframe is fused into the final RENDER pass (which also burns captions),
    and RENDER must follow TRANSCRIBE + CAPTION. The UI stepper displays
    Download -> Transcribe -> Caption -> Render -> Done.
    """

    DOWNLOAD = "download"
    TRANSCRIBE = "transcribe"
    CAPTION = "caption"
    RENDER = "render"
    DONE = "done"
    ERROR = "error"


@dataclass(frozen=True)
class Clip:
    """A single clip definition from the input JSON."""

    id: str
    videoId: str
    url: str
    start: float
    end: float
    title: str
    note: Optional[str] = None
    createdAt: Optional[str] = None

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


@dataclass(frozen=True)
class ProgressEvent:
    """Emitted through a callback as a clip moves through the pipeline.

    `pct` is 0..100 within the current stage (or 100 when the stage completes).
    """

    clip_id: str
    stage: Stage
    pct: float = 0.0
    message: str = ""
    status: str = "running"  # pending | running | done | error


# A stage/observer callback. The pipeline is framework-free; both the CLI and the
# web layer supply their own callback to consume progress.
ProgressCallback = Callable[[ProgressEvent], None]


@dataclass
class ClipResult:
    """Outcome of processing one clip."""

    clip_id: str
    title: str
    status: str  # "done" | "error"
    output_path: Optional[Path] = None
    duration: float = 0.0
    encoder_used: Optional[str] = None
    whisper_device: Optional[str] = None
    error: Optional[str] = None
    timings: dict = field(default_factory=dict)  # Stage.value -> seconds

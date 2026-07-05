"""Transcriber interface + immutable transcript dataclasses.

All returned timings are RELATIVE TO THE START of the media (t=0 = clip start).
Feed the already-cut clip so word timings line up 1:1 with the reframed output.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator


@dataclass(frozen=True, slots=True)
class Word:
    text: str          # normalized: stripped, internal whitespace collapsed
    start: float       # seconds, relative to clip start
    end: float         # seconds; guaranteed end >= start
    probability: float  # 0..1 word confidence


@dataclass(frozen=True, slots=True)
class Segment:
    text: str
    start: float
    end: float
    words: tuple[Word, ...] = ()


@dataclass(frozen=True, slots=True)
class Transcript:
    words: list[Word]
    segments: list[Segment] = field(default_factory=list)
    language: str = ""
    language_probability: float = 0.0
    duration: float = 0.0

    def __iter__(self) -> Iterator[Word]:
        # Bridge to the spec's `-> list[Word]`: list(transcript) == words.
        return iter(self.words)

    def __len__(self) -> int:
        return len(self.words)


class Transcriber(ABC):
    """Swappable transcription backend. Feed the ALREADY-CUT clip (t=0 = clip start)."""

    @abstractmethod
    def transcribe(self, media_path: str | Path, language: str | None = None) -> Transcript:
        ...

    def close(self) -> None:  # optional resource release
        pass

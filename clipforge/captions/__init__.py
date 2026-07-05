"""Caption lane: word timestamps -> karaoke ASS subtitle -> burned in by ffmpeg."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from clipforge.captions.ass import build_ass
from clipforge.captions.grouping import CaptionEvent, group_words, karaoke_centiseconds
from clipforge.captions.presets import CaptionPreset, available_presets, fonts_dir, get_preset
from clipforge.transcribe.base import Word

__all__ = [
    "CaptionEvent",
    "CaptionPreset",
    "CaptionArtifacts",
    "build_captions",
    "group_words",
    "karaoke_centiseconds",
    "build_ass",
    "get_preset",
    "available_presets",
]


@dataclass(frozen=True)
class CaptionArtifacts:
    ass_path: Path | None  # None => no events => render stage omits the ass filter
    fonts_dir: Path
    font_name: str


def build_captions(words: list[Word], preset: CaptionPreset, out_dir: str | Path) -> CaptionArtifacts:
    """Group words, render the ASS file into out_dir, return the burn handoff.

    If there are no events (empty transcript), returns ass_path=None so the render
    stage skips the burn.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    events = group_words(words, preset)
    fdir = fonts_dir()
    if not events:
        return CaptionArtifacts(None, fdir, preset.font_family)
    ass_path = out_dir / "captions.ass"
    ass_path.write_text(build_ass(events, preset), encoding="utf-8")
    return CaptionArtifacts(ass_path, fdir, preset.font_family)

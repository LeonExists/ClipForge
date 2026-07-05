"""Caption presets: style + grouping + animation, addressed by name via a registry.

Colors are ASS &HAABBGGRR literals (alpha, blue, green, red; AA=00 = opaque).
Add alternate presets with more register(...) calls or dataclasses.replace.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class Animation(str, Enum):
    NONE = "none"        # one color, no motion
    KARAOKE = "karaoke"  # \k color sweep white->highlight, no scaling
    POP = "pop"          # spotlight current word (enlarged), past words revert
    BOTH = "both"        # per-word scale pop + color sweep (past words stay highlighted)


@dataclass(frozen=True)
class CaptionPreset:
    name: str
    font_family: str          # MUST equal the font's internal family name
    font_file: str            # repo-relative bundled .ttf
    font_size: int
    primary_colour: str       # &HAABBGGRR — active/sung/highlight
    secondary_colour: str     # &HAABBGGRR — upcoming/inactive
    outline_colour: str
    back_colour: str          # shadow colour with BorderStyle 1
    outline_width: float
    shadow: float
    alignment: int            # numpad; 2 = bottom-center
    margin_v: int
    bold: bool
    words_per_group: int
    max_chars_per_line: int
    animation: Animation
    uppercase: bool
    silence_gap_threshold: float
    hold: float = 0.10
    pull_back: float = 0.05
    margin_l: int = 60
    margin_r: int = 60
    wrap_style: int = 2
    # pop animation timing, in milliseconds (\t uses ms, unlike \k which uses cs)
    pop_grow_ms: int = 130
    pop_settle_ms: int = 130
    pop_scale: int = 116


def fonts_dir() -> Path:
    """Absolute path to the bundled fonts directory (clipforge/assets/fonts)."""
    return Path(__file__).resolve().parent.parent / "assets" / "fonts"


SHORTS_BOLD = CaptionPreset(
    name="shorts_bold",
    font_family="Anton",
    font_file="clipforge/assets/fonts/Anton-Regular.ttf",
    font_size=96,
    primary_colour="&H0000FFFF",    # opaque yellow (active/sung)
    secondary_colour="&H00FFFFFF",  # opaque white (upcoming)
    outline_colour="&H00000000",    # black outline
    back_colour="&H96000000",       # ~59%-transparent black shadow
    outline_width=6.0,
    shadow=2.0,
    alignment=2,
    margin_v=600,                   # lower-middle third of 1920
    bold=False,                     # Anton is single-weight -> avoid faux-bold smear
    words_per_group=3,
    max_chars_per_line=20,
    animation=Animation.BOTH,
    uppercase=True,
    silence_gap_threshold=0.60,
)


_REGISTRY: dict[str, CaptionPreset] = {}


def register(preset: CaptionPreset) -> CaptionPreset:
    if preset.name in _REGISTRY:
        raise ValueError(f"duplicate caption preset: {preset.name}")
    _REGISTRY[preset.name] = preset
    return preset


def get_preset(name: str) -> CaptionPreset:
    try:
        return _REGISTRY[name]
    except KeyError:
        raise KeyError(f"unknown caption preset {name!r}; available: {sorted(_REGISTRY)}")


def available_presets() -> list[str]:
    return sorted(_REGISTRY)


register(SHORTS_BOLD)

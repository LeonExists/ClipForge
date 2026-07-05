"""Pure ASS subtitle generation from CaptionEvents + a preset.

Karaoke color convention (verified visually): PrimaryColour = active/sung
(highlight), SecondaryColour = upcoming/inactive. \\k durations are CENTISECONDS;
\\t animation times are MILLISECONDS (never share a variable).
"""

from __future__ import annotations

from clipforge.captions.grouping import CaptionEvent
from clipforge.captions.presets import Animation, CaptionPreset

# V4+ Style field order (23 fields).
_STYLE_FORMAT = (
    "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
    "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
    "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding"
)
_EVENTS_FORMAT = "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"

_STYLE_NAME = "cf"


def ass_time(t: float) -> str:
    """Format seconds as ASS H:MM:SS.CC (centisecond precision)."""
    cs = int(round(max(0.0, t) * 100))
    return f"{cs // 360000}:{(cs // 6000) % 60:02d}:{(cs // 100) % 60:02d}.{cs % 100:02d}"


def rgb_to_ass(hex_rgb: str, alpha: int = 0) -> str:
    """Convert #RRGGBB (+ optional 0..255 alpha) to an ASS &HAABBGGRR literal."""
    s = hex_rgb.lstrip("#")
    if len(s) != 6:
        raise ValueError(f"expected #RRGGBB, got {hex_rgb!r}")
    rr, gg, bb = s[0:2], s[2:4], s[4:6]
    return f"&H{alpha:02X}{bb.upper()}{gg.upper()}{rr.upper()}"


def _color_override(ass_colour: str) -> str:
    """Turn a Style &HAABBGGRR into an inline \\1c&Hbbggrr& override (drop alpha)."""
    body = ass_colour[2:] if ass_colour.upper().startswith("&H") else ass_colour
    body = body.rstrip("&")
    bbggrr = body[-6:]  # strip the AA byte
    return f"\\1c&H{bbggrr}&"


def escape_text(text: str) -> str:
    """Escape characters special to ASS Dialogue text."""
    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")


def build_header(preset: CaptionPreset, play_w: int = 1080, play_h: int = 1920) -> str:
    return "\n".join([
        "[Script Info]",
        "; ClipForge captions",
        "ScriptType: v4.00+",
        f"PlayResX: {play_w}",
        f"PlayResY: {play_h}",
        "ScaledBorderAndShadow: yes",
        f"WrapStyle: {preset.wrap_style}",
        "YCbCr Matrix: TV.709",
    ])


def build_style_line(preset: CaptionPreset) -> str:
    bold = -1 if preset.bold else 0
    fields = [
        _STYLE_NAME,
        preset.font_family,
        preset.font_size,
        preset.primary_colour,
        preset.secondary_colour,
        preset.outline_colour,
        preset.back_colour,
        bold,
        0,        # Italic
        0,        # Underline
        0,        # StrikeOut
        100,      # ScaleX
        100,      # ScaleY
        0,        # Spacing
        0,        # Angle
        1,        # BorderStyle (1 = outline + shadow)
        preset.outline_width,
        preset.shadow,
        preset.alignment,
        preset.margin_l,
        preset.margin_r,
        preset.margin_v,
        1,        # Encoding
    ]
    return "Style: " + ",".join(str(f) for f in fields)


def _pop_tag(preset: CaptionPreset) -> str:
    """Reset scale to 100 then grow to pop_scale and settle back (times in ms)."""
    g = preset.pop_grow_ms
    s = preset.pop_settle_ms
    sc = preset.pop_scale
    return (
        f"\\fscx100\\fscy100"
        f"\\t(0,{g},\\fscx{sc}\\fscy{sc})"
        f"\\t({g},{g + s},\\fscx100\\fscy100)"
    )


def render_dialogue(event: CaptionEvent, preset: CaptionPreset) -> list[str]:
    """Render one CaptionEvent to one or more Dialogue lines (per animation mode)."""
    texts = [escape_text(t) for t, _ in event.words]
    ks = [k for _, k in event.words]
    n = len(texts)
    secondary = _color_override(preset.secondary_colour)

    if preset.animation in (Animation.NONE, Animation.KARAOKE):
        if preset.animation == Animation.NONE:
            body = " ".join(texts)
        else:  # karaoke: per-word \k sweep, upcoming words in SecondaryColour
            body = " ".join(f"{{\\k{ks[i]}}}{texts[i]}" for i in range(n))
        return [_dialogue_line(event.start, event.end, body)]

    # POP / BOTH: one event per on-screen state (per active word).
    lines: list[str] = []
    cum = 0.0
    pop = _pop_tag(preset)
    for active in range(n):
        seg_start = event.start + cum / 100.0
        cum += ks[active]
        seg_end = event.end if active == n - 1 else event.start + cum / 100.0

        parts: list[str] = []
        for j in range(n):
            if j == active:
                parts.append(f"{{{pop}}}{texts[j]}")
            elif j < active:
                # past words: BOTH keeps them highlighted (inherit Primary); POP reverts to secondary
                if preset.animation == Animation.POP:
                    parts.append(f"{{{secondary}}}{texts[j]}")
                else:
                    parts.append(texts[j])
            else:  # future word
                if j == active + 1:
                    parts.append(f"{{{secondary}}}{texts[j]}")
                else:
                    parts.append(texts[j])
        lines.append(_dialogue_line(seg_start, seg_end, " ".join(parts)))
    return lines


def _dialogue_line(start: float, end: float, text: str) -> str:
    return (
        f"Dialogue: 0,{ass_time(start)},{ass_time(end)},{_STYLE_NAME},,0,0,0,,{text}"
    )


def build_ass(events: list[CaptionEvent], preset: CaptionPreset,
              play_w: int = 1080, play_h: int = 1920) -> str:
    """Assemble a full .ass document. Empty events -> a valid header/style-only file."""
    lines = [
        build_header(preset, play_w, play_h),
        "",
        "[V4+ Styles]",
        _STYLE_FORMAT,
        build_style_line(preset),
        "",
        "[Events]",
        _EVENTS_FORMAT,
    ]
    for ev in events:
        lines.extend(render_dialogue(ev, preset))
    return "\n".join(lines) + "\n"

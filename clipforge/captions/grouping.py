"""Pure phrase-grouping + karaoke centisecond math.

Groups words into caption events (bounded by words_per_group, char width, and
silence gaps), computes each event's on-screen window, and splits its duration into
per-word \\k centiseconds that sum EXACTLY to the event duration.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from clipforge.captions.presets import CaptionPreset
from clipforge.transcribe.base import Word


@dataclass(frozen=True)
class CaptionEvent:
    start: float                          # on-screen window start (s)
    end: float                            # on-screen window end (s)
    words: tuple[tuple[str, int], ...]    # ((rendered_text, k_centiseconds), ...)


def rendered_len(texts: list[str]) -> int:
    """Deterministic width proxy: chars + inter-word spaces."""
    if not texts:
        return 0
    return sum(len(t) for t in texts) + (len(texts) - 1)


def _transform(text: str, uppercase: bool) -> str:
    return text.upper() if uppercase else text


def group_words(words: list[Word], preset: CaptionPreset) -> list[CaptionEvent]:
    """Partition words into caption events, then compute windows + per-word \\k."""
    if not words:
        return []

    wpg = max(1, min(4, preset.words_per_group))
    max_chars = preset.max_chars_per_line
    up = preset.uppercase

    # Pass 1: partition into groups of Word.
    groups: list[list[Word]] = []
    cur: list[Word] = []
    cur_texts: list[str] = []
    for w in words:
        t = _transform(w.text, up)
        if cur:
            gap = w.start - cur[-1].end
            full = len(cur) >= wpg
            overflow = rendered_len([*cur_texts, t]) > max_chars
            silence = gap > preset.silence_gap_threshold
            if full or overflow or silence:
                groups.append(cur)
                cur, cur_texts = [], []
        cur.append(w)
        cur_texts.append(t)
    if cur:
        groups.append(cur)

    # Pass 2: windows (flicker-kill pull-back + trailing hold) then \k.
    events: list[CaptionEvent] = []
    for gi, g in enumerate(groups):
        e_start, e_end = g[0].start, g[-1].end
        if gi > 0:
            prev_end = groups[gi - 1][-1].end
            inter_gap = e_start - prev_end
            if 0 < inter_gap <= preset.silence_gap_threshold:
                # butt up against previous event's end to kill flicker
                e_start = max(prev_end, e_start - preset.pull_back)
            # else leave the gap -> screen clears during the silence
        if gi < len(groups) - 1:
            e_end = min(e_end + preset.hold, groups[gi + 1][0].start)
        else:
            e_end = e_end + preset.hold
        events.append(_build_event(g, e_start, e_end, up))
    return events


def _build_event(g: list[Word], e_start: float, e_end: float, uppercase: bool) -> CaptionEvent:
    n = len(g)
    # Tiling boundaries: window start, each subsequent word start, window end.
    b = [e_start] + [g[i].start for i in range(1, n)] + [e_end]
    for i in range(1, len(b)):
        b[i] = max(b[i], b[i - 1])  # guard monotonicity vs clock jitter
    chunk = [b[i + 1] - b[i] for i in range(n)]  # seconds; sum == e_end - e_start
    total_cs = round(e_end * 100) - round(e_start * 100)  # same rounding as ASS time fmt
    ks = karaoke_centiseconds(chunk, total_cs)
    texts = tuple(_transform(w.text, uppercase) for w in g)
    return CaptionEvent(e_start, e_end, tuple(zip(texts, ks)))


def karaoke_centiseconds(chunk_seconds: list[float], total_cs: int) -> list[int]:
    """Split total_cs across chunks so the result sums EXACTLY to total_cs.

    Floor each chunk's centisecond value, then distribute the leftover centiseconds
    one-by-one to the largest fractional parts (Hamilton / largest-remainder). Ties
    break toward the lower index for determinism.
    """
    n = len(chunk_seconds)
    if n == 0:
        return []
    raw = [max(0.0, c) * 100.0 for c in chunk_seconds]
    base = [int(math.floor(x)) for x in raw]
    frac = [raw[i] - base[i] for i in range(n)]
    remainder = total_cs - sum(base)
    # Clamp defensively; by construction remainder is in [0, n].
    remainder = max(0, min(remainder, n))
    order = sorted(range(n), key=lambda i: (-frac[i], i))
    for i in order[:remainder]:
        base[i] += 1
    # If total_cs was smaller than sum(base) (degenerate), trim from the smallest.
    deficit = sum(base) - total_cs
    if deficit > 0:
        trim_order = sorted(range(n), key=lambda i: (frac[i], i))
        for i in trim_order:
            if deficit == 0:
                break
            if base[i] > 0:
                base[i] -= 1
                deficit -= 1
    return base

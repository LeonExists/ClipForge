"""Pure normalization: faster-whisper segment/info objects -> Transcript.

This is where all clamping / whitespace normalization / sorting lives, and is the
primary unit-test target for the transcribe lane (model inference is mocked).
"""

from __future__ import annotations

from typing import Iterable, Optional

from clipforge.transcribe.base import Segment, Transcript, Word


def normalize_word(
    raw_text: str,
    start: float,
    end: float,
    prob: Optional[float],
    clip_duration: Optional[float] = None,
) -> Word:
    """Strip/collapse whitespace, clamp times, guarantee end>=start and 0<=prob<=1."""
    text = " ".join((raw_text or "").split())  # strips FW leading space + collapses
    start = max(0.0, float(start))
    end = float(end)
    if end < start:
        end = start
    if clip_duration is not None:
        start = min(start, clip_duration)
        end = min(end, clip_duration)
    prob_v = 0.0 if prob is None else min(1.0, max(0.0, float(prob)))
    return Word(text=text, start=start, end=end, probability=prob_v)


def build_transcript(fw_segments: Iterable, info) -> Transcript:
    """Turn faster-whisper's segment generator + info into a Transcript.

    Iterating `fw_segments` is what actually runs inference in faster-whisper.
    Words with empty text after normalization are dropped; segments without word
    timestamps are kept with their stripped text.
    """
    dur = float(getattr(info, "duration", 0.0) or 0.0)
    segments: list[Segment] = []
    words: list[Word] = []
    for seg in fw_segments:
        seg_words: list[Word] = []
        for w in (getattr(seg, "words", None) or []):
            nw = normalize_word(w.word, w.start, w.end, getattr(w, "probability", None), dur)
            if nw.text:
                seg_words.append(nw)
        words.extend(seg_words)
        seg_text = " ".join(x.text for x in seg_words) or (getattr(seg, "text", "") or "").strip()
        seg_start = max(0.0, float(getattr(seg, "start", 0.0)))
        seg_end = float(getattr(seg, "end", 0.0))
        if dur:
            seg_end = min(seg_end, dur)
        segments.append(Segment(text=seg_text, start=seg_start, end=seg_end, words=tuple(seg_words)))

    words.sort(key=lambda x: (x.start, x.end))
    return Transcript(
        words=words,
        segments=segments,
        language=getattr(info, "language", "") or "",
        language_probability=float(getattr(info, "language_probability", 0.0) or 0.0),
        duration=dur,
    )

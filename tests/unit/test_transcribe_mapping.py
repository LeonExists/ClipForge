from types import SimpleNamespace as NS

from clipforge.transcribe.base import Transcript, Word
from clipforge.transcribe.mapping import build_transcript, normalize_word


def test_normalize_strips_leading_space_and_collapses():
    w = normalize_word(" Hello   world ", 0.1, 0.4, 0.9)
    assert w.text == "Hello world"


def test_normalize_probability_clamped():
    assert normalize_word("a", 0, 1, None).probability == 0.0
    assert normalize_word("a", 0, 1, 1.7).probability == 1.0
    assert normalize_word("a", 0, 1, -0.3).probability == 0.0


def test_normalize_end_ge_start():
    w = normalize_word("a", 1.0, 0.5, 0.9)
    assert w.end == w.start == 1.0


def test_normalize_clamps_to_duration():
    w = normalize_word("a", 40.0, 50.0, 0.9, clip_duration=30.0)
    assert w.start == 30.0 and w.end == 30.0


def test_normalize_negative_start_zeroed():
    w = normalize_word("a", -2.0, 1.0, 0.9)
    assert w.start == 0.0


def _fake(words_per_seg, dur=30.0, lang="en"):
    segs = []
    for seg_words in words_per_seg:
        w_objs = [NS(word=t, start=s, end=e, probability=p) for (t, s, e, p) in seg_words]
        text = " ".join(t.strip() for (t, *_ ) in seg_words)
        start = seg_words[0][1] if seg_words else 0.0
        end = seg_words[-1][2] if seg_words else 0.0
        segs.append(NS(text=text, start=start, end=end, words=w_objs))
    return segs, NS(language=lang, language_probability=0.99, duration=dur)


def test_build_transcript_flattens_and_sorts():
    segs, info = _fake([
        [(" Hello", 0.1, 0.4, 0.9), (" world", 0.4, 0.8, 0.9)],
        [(" again", 1.0, 1.4, 0.9)],
    ])
    t = build_transcript(segs, info)
    assert [w.text for w in t.words] == ["Hello", "world", "again"]
    assert t.language == "en"
    assert t.duration == 30.0


def test_build_transcript_drops_empty_text():
    segs, info = _fake([[("  ", 0.0, 0.2, 0.9), ("hi", 0.2, 0.5, 0.9)]])
    t = build_transcript(segs, info)
    assert [w.text for w in t.words] == ["hi"]


def test_build_transcript_segment_without_words():
    segs = [NS(text="no word timestamps", start=0.0, end=2.0, words=None)]
    info = NS(language="en", language_probability=0.9, duration=5.0)
    t = build_transcript(segs, info)
    assert t.words == []
    assert t.segments[0].text == "no word timestamps"


def test_build_transcript_empty():
    info = NS(language="", language_probability=0.0, duration=15.0)
    t = build_transcript([], info)
    assert t.words == []
    assert len(t) == 0
    assert list(t) == []


def test_transcript_iter_bridge():
    t = Transcript(words=[Word("a", 0, 1, 0.9), Word("b", 1, 2, 0.9)])
    assert list(t) == t.words
    assert len(t) == 2

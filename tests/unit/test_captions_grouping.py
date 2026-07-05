import random

from clipforge.captions.grouping import (
    CaptionEvent,
    group_words,
    karaoke_centiseconds,
    rendered_len,
)
from clipforge.captions.presets import SHORTS_BOLD, Animation
from clipforge.transcribe.base import Word
from dataclasses import replace


def W(text, start, end):
    return Word(text, start, end, 0.9)


def test_word_cap_boundaries():
    p = replace(SHORTS_BOLD, words_per_group=3, max_chars_per_line=999, silence_gap_threshold=99)
    words = [W(f"w{i}", i * 0.5, i * 0.5 + 0.4) for i in range(7)]
    events = group_words(words, p)
    counts = [len(e.words) for e in events]
    assert counts == [3, 3, 1]


def test_char_overflow_closes_early():
    p = replace(SHORTS_BOLD, words_per_group=4, max_chars_per_line=12,
                silence_gap_threshold=99, uppercase=False)
    # "hello"(5)+" "+"world"(5) = 11 ok; adding +" "+"again"(5)=17 > 12 -> close at 2.
    words = [W("hello", 0, 0.4), W("world", 0.4, 0.8), W("again", 0.8, 1.2)]
    events = group_words(words, p)
    assert [len(e.words) for e in events] == [2, 1]
    # overflowing word is never dropped
    assert events[1].words[0][0] == "again"


def test_silence_gap_split():
    p = replace(SHORTS_BOLD, words_per_group=9, max_chars_per_line=999, silence_gap_threshold=0.5)
    words = [W("a", 0, 0.4), W("b", 0.45, 0.8), W("c", 2.0, 2.4)]  # big gap before c
    events = group_words(words, p)
    assert len(events) == 2
    assert [t for t, _ in events[0].words] == ["A", "B"]
    assert [t for t, _ in events[1].words] == ["C"]


def test_ksum_exact_named():
    # THE invariant: per-word \k sums EXACTLY to the event centisecond duration.
    p = replace(SHORTS_BOLD, words_per_group=4, max_chars_per_line=999, silence_gap_threshold=99)
    words = [W("a", 1.00, 1.40), W("b", 1.40, 1.95), W("c", 1.95, 2.33)]
    events = group_words(words, p)
    for e in events:
        window_cs = round(e.end * 100) - round(e.start * 100)
        assert sum(k for _, k in e.words) == window_cs


def test_karaoke_centiseconds_worked_example():
    ks = karaoke_centiseconds([0.283, 0.323, 0.345, 0.549], 150)
    assert sum(ks) == 150
    assert ks == [28, 32, 35, 55]


def test_karaoke_centiseconds_random_sums_exact():
    rng = random.Random(1234)
    for _ in range(500):
        n = rng.randint(1, 6)
        chunks = [rng.uniform(0.01, 2.0) for _ in range(n)]
        total = round(sum(chunks) * 100)
        ks = karaoke_centiseconds(chunks, total)
        assert sum(ks) == total
        assert all(k >= 0 for k in ks)


def test_karaoke_centiseconds_deterministic():
    a = karaoke_centiseconds([0.1, 0.2, 0.3], 60)
    b = karaoke_centiseconds([0.1, 0.2, 0.3], 60)
    assert a == b


def test_empty_words():
    assert group_words([], SHORTS_BOLD) == []


def test_rendered_len():
    assert rendered_len([]) == 0
    assert rendered_len(["ab", "cd"]) == 5  # 2 + 1 space + 2


def test_uppercase_applied_and_affects_width():
    p_upper = replace(SHORTS_BOLD, uppercase=True, words_per_group=9,
                      max_chars_per_line=999, silence_gap_threshold=99)
    words = [W("hi", 0, 0.4)]
    ev = group_words(words, p_upper)[0]
    assert ev.words[0][0] == "HI"

from dataclasses import replace

from clipforge.captions.ass import (
    _EVENTS_FORMAT,
    _STYLE_FORMAT,
    ass_time,
    build_ass,
    build_style_line,
    escape_text,
    rgb_to_ass,
    render_dialogue,
)
from clipforge.captions.grouping import CaptionEvent
from clipforge.captions.presets import SHORTS_BOLD, Animation


def test_ass_time_format():
    assert ass_time(0.0) == "0:00:00.00"
    assert ass_time(1.6) == "0:00:01.60"
    assert ass_time(61.5) == "0:01:01.50"
    assert ass_time(3661.0) == "1:01:01.00"


def test_ass_time_clamps_negative():
    assert ass_time(-5.0) == "0:00:00.00"


def test_rgb_to_ass_byte_order():
    # #RRGGBB -> &HAABBGGRR (alpha, blue, green, red)
    assert rgb_to_ass("#FFFF00") == "&H0000FFFF"   # yellow
    assert rgb_to_ass("#FFFFFF") == "&H00FFFFFF"   # white
    assert rgb_to_ass("#000000") == "&H00000000"   # black
    assert rgb_to_ass("#FF0000") == "&H000000FF"   # red -> BB=00 GG=00 RR=FF
    assert rgb_to_ass("#123456", alpha=0x80) == "&H80563412"


def test_escape_text():
    assert escape_text("a{b}c") == "a\\{b\\}c"
    assert escape_text("a\\b") == "a\\\\b"


def test_style_line_field_count():
    line = build_style_line(SHORTS_BOLD)
    assert line.startswith("Style: ")
    fields = line[len("Style: "):].split(",")
    # 23 V4+ style fields
    assert len(fields) == 23


def test_style_format_field_count_matches():
    fmt_fields = _STYLE_FORMAT[len("Format: "):].split(", ")
    assert len(fmt_fields) == 23


def test_bold_false_for_anton():
    # shorts_bold uses bold=False -> Bold field must be 0 (avoid faux-bold smear)
    line = build_style_line(SHORTS_BOLD)
    fields = line[len("Style: "):].split(",")
    assert fields[7] == "0"


def test_karaoke_line_has_k_tags():
    p = replace(SHORTS_BOLD, animation=Animation.KARAOKE)
    ev = CaptionEvent(0.0, 1.0, (("HELLO", 40), ("THERE", 60)))
    lines = render_dialogue(ev, p)
    assert len(lines) == 1
    assert "{\\k40}HELLO" in lines[0]
    assert "{\\k60}THERE" in lines[0]


def test_both_animation_one_event_per_word():
    p = replace(SHORTS_BOLD, animation=Animation.BOTH)
    ev = CaptionEvent(0.0, 1.0, (("A", 30), ("B", 30), ("C", 40)))
    lines = render_dialogue(ev, p)
    assert len(lines) == 3  # one per active word
    # active word carries the pop scale tag
    assert "\\fscx" in lines[0]


def test_both_future_word_gets_secondary_color():
    p = replace(SHORTS_BOLD, animation=Animation.BOTH)
    ev = CaptionEvent(0.0, 1.0, (("A", 50), ("B", 50)))
    lines = render_dialogue(ev, p)
    # first line: A active, B is future -> should carry a \1c override (secondary=white)
    assert "\\1c" in lines[0]


def test_none_animation_single_plain_line():
    p = replace(SHORTS_BOLD, animation=Animation.NONE)
    ev = CaptionEvent(0.0, 1.0, (("A", 50), ("B", 50)))
    lines = render_dialogue(ev, p)
    assert len(lines) == 1
    assert "\\k" not in lines[0]
    assert "A B" in lines[0]


def test_empty_events_valid_ass():
    doc = build_ass([], SHORTS_BOLD)
    assert "[Script Info]" in doc
    assert "PlayResX: 1080" in doc
    assert "PlayResY: 1920" in doc
    assert "[V4+ Styles]" in doc
    assert "[Events]" in doc
    assert "Dialogue:" not in doc


def test_full_doc_contains_events_format():
    ev = CaptionEvent(0.0, 1.0, (("HI", 100),))
    doc = build_ass([ev], SHORTS_BOLD)
    assert _EVENTS_FORMAT in doc
    assert "Dialogue:" in doc

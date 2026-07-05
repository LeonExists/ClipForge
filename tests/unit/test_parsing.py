import pytest

from clipforge.parsing import ClipParseError, parse_clips, parse_clips_text

SAMPLE = [
    {
        "createdAt": "2026-07-03T14:48:23.279Z",
        "end": 36.33,
        "id": "Q260EqSF5aA-1783090103279-3cj9fk",
        "note": "",
        "start": 21.61,
        "title": "Stable Ronaldo's Funniest Moments!",
        "url": "https://www.youtube.com/watch?v=Q260EqSF5aA",
        "videoId": "Q260EqSF5aA",
    },
]


def test_happy_path():
    clips = parse_clips(SAMPLE)
    assert len(clips) == 1
    c = clips[0]
    assert c.id == "Q260EqSF5aA-1783090103279-3cj9fk"
    assert c.videoId == "Q260EqSF5aA"
    assert c.start == 21.61 and c.end == 36.33
    assert abs(c.duration - 14.72) < 1e-9
    assert c.note == ""


def test_note_optional():
    entry = dict(SAMPLE[0])
    del entry["note"]
    clips = parse_clips([entry])
    assert clips[0].note is None


def test_root_must_be_array():
    with pytest.raises(ClipParseError):
        parse_clips({"not": "an array"})


def test_entry_must_be_object():
    with pytest.raises(ClipParseError) as ei:
        parse_clips([SAMPLE[0], "nope"])
    assert any("must be an object" in e for e in ei.value.errors)


def test_missing_required_string():
    entry = dict(SAMPLE[0])
    del entry["url"]
    with pytest.raises(ClipParseError) as ei:
        parse_clips([entry])
    assert any(".url" in e for e in ei.value.errors)


def test_empty_string_field_rejected():
    entry = dict(SAMPLE[0], title="   ")
    with pytest.raises(ClipParseError) as ei:
        parse_clips([entry])
    assert any(".title" in e for e in ei.value.errors)


def test_start_ge_end_rejected():
    entry = dict(SAMPLE[0], start=40.0, end=36.33)
    with pytest.raises(ClipParseError) as ei:
        parse_clips([entry])
    assert any("end must be greater than start" in e for e in ei.value.errors)


def test_negative_start_rejected():
    entry = dict(SAMPLE[0], start=-1.0, end=5.0)
    with pytest.raises(ClipParseError) as ei:
        parse_clips([entry])
    assert any("start must be >= 0" in e for e in ei.value.errors)


def test_non_numeric_range_rejected():
    entry = dict(SAMPLE[0], end="36.33")
    with pytest.raises(ClipParseError) as ei:
        parse_clips([entry])
    assert any(".end must be a number" in e for e in ei.value.errors)


def test_bool_is_not_a_number():
    entry = dict(SAMPLE[0], start=True)
    with pytest.raises(ClipParseError):
        parse_clips([entry])


def test_duplicate_ids_rejected():
    with pytest.raises(ClipParseError) as ei:
        parse_clips([SAMPLE[0], dict(SAMPLE[0])])
    assert any("duplicate" in e for e in ei.value.errors)


def test_note_wrong_type_rejected():
    entry = dict(SAMPLE[0], note=123)
    with pytest.raises(ClipParseError):
        parse_clips([entry])


def test_extra_keys_tolerated():
    entry = dict(SAMPLE[0], somethingExtra="ok")
    clips = parse_clips([entry])
    assert len(clips) == 1


def test_parse_text_malformed_json():
    with pytest.raises(ClipParseError) as ei:
        parse_clips_text("{not valid json")
    assert any("invalid JSON" in e for e in ei.value.errors)


def test_parse_text_valid():
    import json

    clips = parse_clips_text(json.dumps(SAMPLE))
    assert len(clips) == 1


def test_aggregates_multiple_errors():
    bad = {"id": "", "videoId": "", "url": "", "title": "", "start": "x", "end": "y"}
    with pytest.raises(ClipParseError) as ei:
        parse_clips([bad])
    # several field problems reported at once
    assert len(ei.value.errors) >= 4

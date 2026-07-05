from clipforge.naming import output_name, short_hash, slugify


def test_basic_slug():
    assert slugify("Stable Ronaldo's Funniest Moments!") == "stable-ronaldo-s-funniest-moments"


def test_spaces_and_punctuation_collapse():
    assert slugify("Hello,   World!!!") == "hello-world"


def test_unicode_accents_stripped():
    assert slugify("Café déjà vu") == "cafe-deja-vu"


def test_leading_trailing_trimmed():
    assert slugify("---Hello---") == "hello"


def test_length_capped():
    s = slugify("a" * 200, max_len=80)
    assert len(s) <= 80


def test_empty_title_fallback():
    assert slugify("") == "clip"
    assert slugify("!!!") == "clip"


def test_windows_reserved_name_guarded():
    # "CON" slugs to "con" which is reserved -> must be escaped.
    assert slugify("CON") != "con"
    assert slugify("NUL") != "nul"
    assert slugify("com1") != "com1"


def test_short_hash_deterministic():
    assert short_hash("abc") == short_hash("abc")
    assert len(short_hash("abc")) == 8


def test_short_hash_distinguishes_ids():
    assert short_hash("id-one") != short_hash("id-two")


def test_output_name_shape():
    name = output_name("Stable Ronaldo's Funniest Moments!", "Q260EqSF5aA-123-abc")
    assert name.endswith(".mp4")
    assert name.startswith("stable-ronaldo-s-funniest-moments-")


def test_same_title_different_ids_distinct_files():
    a = output_name("Same Title", "id-1")
    b = output_name("Same Title", "id-2")
    assert a != b
    # only the hash suffix differs
    assert a.rsplit("-", 1)[0] == b.rsplit("-", 1)[0]

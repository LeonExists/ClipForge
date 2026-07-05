from clipforge.download.progress import parse_progress


def _line(status="downloading", dl="NA", tot="NA", est="NA", fi="NA", fn="NA", eta="NA", spd="NA"):
    return f"download:__CFDL__\t{status}\t{dl}\t{tot}\t{est}\t{fi}\t{fn}\t{eta}\t{spd}"


def test_ignores_non_sentinel_lines():
    assert parse_progress("[youtube] extracting ...") is None
    assert parse_progress("some random output") is None


def test_fraction_from_total_bytes():
    p = parse_progress(_line(dl="500", tot="1000"))
    assert p is not None
    assert p.fraction == 0.5


def test_fraction_from_estimate_when_no_total():
    p = parse_progress(_line(dl="250", tot="NA", est="1000"))
    assert p.fraction == 0.25


def test_fragment_fallback():
    p = parse_progress(_line(dl="NA", tot="NA", est="NA", fi="2", fn="4"))
    assert p.fraction == 0.5


def test_finished_reserves_tail():
    p = parse_progress(_line(status="finished", dl="1000", tot="1000"))
    assert p.fraction == 0.99


def test_fraction_clamped():
    p = parse_progress(_line(dl="1500", tot="1000"))
    assert p.fraction == 1.0


def test_na_fields_yield_none_fraction():
    p = parse_progress(_line())
    assert p is not None
    assert p.fraction is None


def test_eta_and_speed_parsed():
    p = parse_progress(_line(dl="500", tot="1000", eta="12", spd="2048000"))
    assert p.eta == 12.0
    assert p.speed == 2048000.0

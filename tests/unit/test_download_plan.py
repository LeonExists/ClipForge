import pytest

from clipforge.config import Config
from clipforge.download.plan import (
    DownloadMode,
    group_by_video_id,
    plan_downloads,
    validate_range,
)
from clipforge.errors import InvalidRangeError
from clipforge.models import Clip


def C(id, vid, start, end):
    return Clip(id=id, videoId=vid, url=f"https://y/{vid}", start=start, end=end, title="t")


def test_group_by_video_id_preserves_order():
    clips = [C("1", "A", 0, 1), C("2", "B", 0, 1), C("3", "A", 2, 3)]
    groups = group_by_video_id(clips)
    assert list(groups.keys()) == ["A", "B"]
    assert len(groups["A"]) == 2 and len(groups["B"]) == 1


def test_validate_range_rejects_start_ge_end():
    with pytest.raises(InvalidRangeError):
        validate_range(C("1", "A", 5, 5))


def test_validate_range_rejects_negative_start():
    with pytest.raises(InvalidRangeError):
        validate_range(C("1", "A", -1, 5))


def test_single_clip_is_ranged():
    plans = plan_downloads([C("1", "A", 0, 5)], Config())
    assert len(plans) == 1
    assert plans[0].mode == DownloadMode.RANGED


def test_default_grouping_is_ranged_even_for_multi():
    # The sample: 3 clips same videoId, default download_grouping="ranged".
    clips = [C("1", "A", 21.6, 36.3), C("2", "A", 529.9, 541.8), C("3", "A", 669.5, 710.8)]
    plans = plan_downloads(clips, Config())  # default ranged
    assert len(plans) == 1
    assert plans[0].mode == DownloadMode.RANGED
    assert len(plans[0].clips) == 3


def test_covering_forced():
    clips = [C("1", "A", 10, 15), C("2", "A", 16, 20)]
    cfg = Config(download_grouping="covering")
    plans = plan_downloads(clips, cfg)
    assert plans[0].mode == DownloadMode.COVERING
    assert plans[0].cover_start == pytest.approx(9.5)  # 10 - pad(0.5)
    assert plans[0].cover_end == pytest.approx(20.5)


def test_auto_picks_covering_when_clustered():
    # clips clustered: span 10..20 = 10s, sum spans = 5+4 = 9s -> span <= 9*1.5 -> covering
    clips = [C("1", "A", 10, 15), C("2", "A", 16, 20)]
    cfg = Config(download_grouping="auto")
    plans = plan_downloads(clips, cfg)
    assert plans[0].mode == DownloadMode.COVERING


def test_auto_picks_ranged_when_scattered():
    # clips far apart: span huge vs tiny sum, and gap >> gap_budget -> ranged
    clips = [C("1", "A", 0, 3), C("2", "A", 3600, 3603)]
    cfg = Config(download_grouping="auto", covering_gap_budget_sec=30, covering_overhead_factor=1.5)
    plans = plan_downloads(clips, cfg)
    assert plans[0].mode == DownloadMode.RANGED

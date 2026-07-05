from clipforge.config import Config
from clipforge.ffmpeg import SourceInfo, escape_filter_path
from clipforge.reframe import (
    BlurPadReframer,
    CropReframer,
    compose_final_graph,
    get_reframer,
)

CFG = Config()
SRC = SourceInfo(path="in.mp4", width=1280, height=720)


def test_crop_graph():
    rg = CropReframer().build_reframe(SRC, CFG)
    assert rg.out_label == "vr"
    assert len(rg.chains) == 1
    g = rg.chains[0]
    assert "crop='min(iw,ih*1080/1920)':'min(ih,iw*1920/1080)'" in g
    assert "scale=1080:1920" in g
    assert "setsar=1" in g


def test_blur_pad_graph():
    rg = BlurPadReframer().build_reframe(SRC, CFG)
    assert rg.out_label == "vr"
    assert len(rg.chains) == 4
    joined = ";".join(rg.chains)
    assert "split=2[bg][fg]" in joined
    assert "force_original_aspect_ratio=increase" in joined
    assert "force_original_aspect_ratio=decrease" in joined
    assert "gblur=sigma=20" in joined
    assert "overlay=(W-w)/2:(H-h)/2" in joined


def test_blur_pad_sigma_configurable():
    cfg = Config(blur_sigma=35)
    rg = BlurPadReframer().build_reframe(SRC, cfg)
    assert "gblur=sigma=35" in ";".join(rg.chains)


def test_get_reframer_unknown_raises():
    import pytest

    with pytest.raises(ValueError):
        get_reframer("auto_reframe")  # future mode, not registered in v1


def test_compose_with_captions_appends_ass():
    rg = CropReframer().build_reframe(SRC, CFG)
    fc, label = compose_final_graph(rg, "captions.ass", "C:/fonts", use_bare_ass_name=True)
    assert label == "vout"
    assert "ass='captions.ass'" in fc
    assert "fontsdir='C\\:/fonts'" in fc
    assert "format=yuv420p[vout]" in fc


def test_compose_without_captions_only_format():
    rg = CropReframer().build_reframe(SRC, CFG)
    fc, label = compose_final_graph(rg, None, None)
    assert label == "vout"
    assert "ass=" not in fc
    assert fc.endswith("format=yuv420p[vout]")


def test_escape_filter_path():
    assert escape_filter_path("C:\\Users\\a b\\cap.ass") == "C\\:/Users/a b/cap.ass"
    assert escape_filter_path("C:/already/forward.ass") == "C\\:/already/forward.ass"
    # non-drive-prefixed path: no leading colon to escape
    assert escape_filter_path("relative/dir") == "relative/dir"

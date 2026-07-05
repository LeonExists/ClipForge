import pytest

from clipforge.encode import build_render_argv
from clipforge.errors import EncodeError


def test_qsv_flags():
    argv = build_render_argv("in.mp4", "out.mp4", "[0:v]scale=1080:1920[vout]", "vout", "h264_qsv", 23)
    assert "h264_qsv" in argv
    assert "-global_quality" in argv
    assert argv[argv.index("-global_quality") + 1] == "23"


def test_libx264_uses_lower_crf():
    argv = build_render_argv("in.mp4", "out.mp4", "fc", "vout", "libx264", 23)
    assert "libx264" in argv
    # crf offset: quality-4
    assert argv[argv.index("-crf") + 1] == "19"


def test_nvenc_flags():
    argv = build_render_argv("in.mp4", "out.mp4", "fc", "vout", "h264_nvenc", 23)
    assert "-cq" in argv and "h264_nvenc" in argv


def test_always_aac_and_faststart():
    argv = build_render_argv("in.mp4", "out.mp4", "fc", "vout", "h264_qsv", 23, "160k")
    assert "-c:a" in argv and "aac" in argv
    assert argv[argv.index("-b:a") + 1] == "160k"
    assert "+faststart" in argv


def test_maps_video_and_optional_audio():
    argv = build_render_argv("in.mp4", "out.mp4", "fc", "vout", "libx264", 23)
    assert "-map" in argv
    assert "[vout]" in argv
    assert "0:a?" in argv


def test_unknown_encoder_raises():
    with pytest.raises(EncodeError):
        build_render_argv("in.mp4", "out.mp4", "fc", "vout", "h265_magic", 23)

from clipforge.config import Config
from clipforge.download.args import (
    build_metadata_argv,
    build_slice_argv,
    build_ytdlp_argv,
    default_out_template,
)


def test_ranged_argv_download_sections_format():
    argv = build_ytdlp_argv("https://y/A", 21.61, 36.33, "out.%(ext)s", Config())
    assert "--download-sections" in argv
    i = argv.index("--download-sections")
    assert argv[i + 1] == "*21.61-36.33"


def test_precise_cuts_adds_force_keyframes():
    argv = build_ytdlp_argv("u", 1, 2, "o", Config(precise_cuts=True))
    assert "--force-keyframes-at-cuts" in argv


def test_no_precise_cuts_omits_force_keyframes():
    argv = build_ytdlp_argv("u", 1, 2, "o", Config(precise_cuts=False))
    assert "--force-keyframes-at-cuts" not in argv


def test_format_selector_included():
    cfg = Config()
    argv = build_ytdlp_argv("u", 1, 2, "o", cfg)
    i = argv.index("-f")
    assert argv[i + 1] == cfg.download_format


def test_default_format_is_hls_first():
    # HLS (m3u8) is segment-addressable, so --download-sections stays truly ranged
    # instead of routing to ffmpeg's whole-file byte-seek on fragmented DASH.
    fmt = Config().download_format
    assert "protocol*=m3u8" in fmt
    assert fmt.index("m3u8") < fmt.index("https")  # HLS is preferred over progressive https
    # Must NOT lead with the old fragmented-DASH selector that caused the stall.
    assert not fmt.startswith("bv*[ext=mp4]")


def test_default_format_caps_height_at_1080():
    assert "height<=1080" in Config().download_format


def test_download_format_override_is_used_verbatim():
    cfg = Config(download_format="18")
    argv = build_ytdlp_argv("u", 1, 2, "o", cfg)
    assert argv[argv.index("-f") + 1] == "18"


def test_argv_is_list_no_shell_string():
    argv = build_ytdlp_argv("u", 1, 2, "o", Config())
    assert isinstance(argv, list)
    assert all(isinstance(a, str) for a in argv)


def test_time_formatting_trims_zeros():
    argv = build_ytdlp_argv("u", 5.0, 10.500, "o", Config())
    i = argv.index("--download-sections")
    assert argv[i + 1] == "*5-10.5"


def test_metadata_argv_skip_download():
    argv = build_metadata_argv("https://y/A")
    assert "--skip-download" in argv
    assert argv[-1] == "https://y/A"


def test_slice_argv_copy_when_no_precise():
    argv = build_slice_argv("cover.mp4", "clip.mp4", 5.0, 3.0, Config(precise_cuts=False))
    assert "-ss" in argv and "-t" in argv
    assert "-c" in argv and "copy" in argv
    assert argv[argv.index("-ss") + 1] == "5"
    assert argv[argv.index("-t") + 1] == "3"


def test_slice_argv_reencode_when_precise_with_encoder():
    argv = build_slice_argv("cover.mp4", "clip.mp4", 5.0, 3.0, Config(precise_cuts=True), "h264_qsv")
    assert "h264_qsv" in argv
    assert "aac" in argv


def test_default_out_template_shape():
    tmpl = default_out_template("/tmp/work", "VID", 1.5, 3.0)
    assert "VID__1.5-3" in tmpl
    assert tmpl.endswith(".%(ext)s")

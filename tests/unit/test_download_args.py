from clipforge.config import Config
from clipforge.download.args import (
    build_metadata_argv,
    build_slice_argv,
    build_ytdlp_argv,
    build_ytdlp_full_argv,
    default_out_template,
    full_format_selector,
    ranged_format_selector,
    source_out_template,
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


def test_ranged_selector_used_in_argv():
    cfg = Config()
    argv = build_ytdlp_argv("u", 1, 2, "o", cfg)
    i = argv.index("-f")
    assert argv[i + 1] == ranged_format_selector(cfg)


def test_ranged_selector_is_hls_only():
    # HLS (m3u8) is segment-addressable, so --download-sections stays truly ranged
    # instead of routing to ffmpeg's whole-file byte-seek on fragmented DASH. It must
    # NOT list progressive 360p — a ranged miss should fall to the native full
    # download (full quality), not silently degrade.
    sel = ranged_format_selector(Config())
    assert "protocol*=m3u8" in sel
    assert "/18" not in sel  # no 360p degradation path
    assert not sel.startswith("bv*[ext=mp4]")  # not the old fragmented-DASH lead


def test_ranged_selector_caps_height():
    assert "height<=1080" in ranged_format_selector(Config())
    assert "height<=720" in ranged_format_selector(Config(download_max_height=720))


def test_full_selector_prefers_h264_and_caps_height():
    sel = full_format_selector(Config())
    assert "vcodec^=avc1" in sel  # H.264 preferred (cheaper decode than AV1)
    assert "height<=1080" in sel


def test_full_argv_has_no_download_sections():
    # The native full download must NOT use --download-sections (that's what stalls
    # on fragmented DASH); this is the reliable full-quality fallback.
    argv = build_ytdlp_full_argv("u", "o", Config())
    assert "--download-sections" not in argv
    assert "--force-keyframes-at-cuts" not in argv
    assert argv[argv.index("-f") + 1] == full_format_selector(Config())


def test_ranged_format_override_is_used_verbatim():
    cfg = Config(download_format="18")
    argv = build_ytdlp_argv("u", 1, 2, "o", cfg)
    assert argv[argv.index("-f") + 1] == "18"


def test_full_format_override_is_used_verbatim():
    assert full_format_selector(Config(download_full_format="99")) == "99"


def test_source_out_template_shape():
    tmpl = source_out_template("/tmp/work", "VID")
    assert "VID__source" in tmpl
    assert tmpl.endswith(".%(ext)s")


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

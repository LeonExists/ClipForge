"""The download stage must reject an audio-only result at fetch time.

Regression guard for the '--download-sections routes to the ffmpeg downloader,
which on a non-seekable (fragmented DASH) source stalls AND drops the video track'
bug: the merged file then had only an aac stream, and the failure surfaced far
downstream as ffmpeg.py's cryptic 'no video stream' at the render step. These
tests pin the behaviour that a missing video stream fails fast, typed, at DOWNLOAD.
"""

from __future__ import annotations

import pytest

from clipforge.config import Config
from clipforge.download.downloader import SegmentDownloader
from clipforge.errors import NoVideoStreamError
from clipforge.ffmpeg import probe_has_video_stream
from clipforge.models import Clip
from clipforge.runner import CommandResult


def _clip():
    return Clip(id="c1", videoId="V", url="https://y/V", start=21.61, end=36.33, title="t")


# -- probe_has_video_stream (pure over the ffprobe seam) --------------------

def test_probe_has_video_true_when_video_stream_present(fake_runner):
    r = fake_runner(stdout="video\n")
    assert probe_has_video_stream(r, "seg.mp4") is True


def test_probe_has_video_false_for_audio_only(fake_runner):
    # ffprobe -select_streams v prints nothing when there is no video stream.
    r = fake_runner(stdout="")
    assert probe_has_video_stream(r, "seg.mp4") is False


def test_probe_has_video_false_when_ffprobe_errors(fake_runner):
    r = fake_runner(returncode=1, stderr="boom")
    assert probe_has_video_stream(r, "seg.mp4") is False


# -- fetch_ranged: ranged success + native-full-download fallback -----------

class _PathAwareRunner:
    """Fake Runner whose ffprobe verdict depends on the file being probed.

    Models the real scenario: the ranged HLS attempt may yield an audio-only file
    (no video), while the native full-source download has video. `video_paths` is a
    list of substrings; a probed path matching any of them reports a video stream.
    Records ffmpeg calls so tests can assert a local slice happened.
    """

    def __init__(self, video_paths):
        self.video_paths = video_paths
        self.ffmpeg_calls: list[list[str]] = []
        self.ytdlp_calls: list[list[str]] = []

    def _res(self, argv, stdout=""):
        return CommandResult(list(argv), 0, stdout, "")

    def ytdlp_streaming(self, args, on_line, **kw):
        self.ytdlp_calls.append(list(args))
        return self._res(args)

    def ytdlp(self, args, **kw):
        return self._res(args)

    def ffprobe(self, args, **kw):
        path = args[-1]
        has_video = any(v in path for v in self.video_paths)
        return self._res(args, stdout="video\n" if has_video else "")

    def ffmpeg(self, args, **kw):
        self.ffmpeg_calls.append(list(args))
        return self._res(args)


def _seed_output(monkeypatch, tmp_path, mapping):
    """Route glob.glob to the right on-disk file per pattern substring."""
    for _, name in mapping.items():
        (tmp_path / name).write_bytes(b"\x00")

    def fake_glob(pat):
        for key, name in mapping.items():
            if key in pat:
                return [str(tmp_path / name)]
        return []

    monkeypatch.setattr("clipforge.download.downloader.glob.glob", fake_glob)


def test_fetch_ranged_accepts_when_video_present(tmp_path, monkeypatch):
    r = _PathAwareRunner(video_paths=["21.61-36.33"])
    dl = SegmentDownloader(r, Config(clamp_end_to_duration=False), tmp_path)
    _seed_output(monkeypatch, tmp_path, {"21.61-36.33": "V__21.61-36.33.mp4"})

    seg = dl.fetch_ranged(_clip(), lambda frac, status: None)
    assert seg.path.endswith("V__21.61-36.33.mp4")
    assert r.ffmpeg_calls == []  # ranged success => no local slice


def test_fetch_ranged_falls_back_to_full_source_when_audio_only(tmp_path, monkeypatch):
    """Ranged HLS audio-only => native full download + local slice (full quality)."""
    # Only the __source file has video; the ranged output is audio-only.
    r = _PathAwareRunner(video_paths=["__source", "__c1.mp4"])
    dl = SegmentDownloader(r, Config(clamp_end_to_duration=False, precise_cuts=False), tmp_path)
    _seed_output(monkeypatch, tmp_path, {
        "21.61-36.33": "V__21.61-36.33.mp4",  # ranged: audio-only
        "__source": "V__source.mp4",           # native full: has video
    })

    seg = dl.fetch_ranged(_clip(), lambda frac, status: None)
    # Sliced locally out of the full source into the per-clip file.
    assert seg.path.endswith("V__c1.mp4")
    assert len(r.ffmpeg_calls) == 1  # exactly one local slice
    # Slice offset is the ABSOLUTE clip start (source begins at t=0), not relative.
    slice_argv = r.ffmpeg_calls[0]
    assert slice_argv[slice_argv.index("-ss") + 1] == "21.61"


def test_full_source_cached_across_clips(tmp_path, monkeypatch):
    """Two clips from one video download the native source at most once."""
    r = _PathAwareRunner(video_paths=["__source", "__c1.mp4", "__c2.mp4"])
    dl = SegmentDownloader(r, Config(clamp_end_to_duration=False, precise_cuts=False), tmp_path)
    _seed_output(monkeypatch, tmp_path, {
        "21.61-36.33": "V__21.61-36.33.mp4",
        "__source": "V__source.mp4",
    })

    c1 = Clip(id="c1", videoId="V", url="https://y/V", start=21.61, end=36.33, title="t")
    c2 = Clip(id="c2", videoId="V", url="https://y/V", start=21.61, end=36.33, title="t")
    dl.fetch_ranged(c1, lambda f, s: None)
    dl.fetch_ranged(c2, lambda f, s: None)

    # ytdlp called: ranged(c1), full-source(c1), ranged(c2)  -- NOT full-source(c2).
    source_dls = [a for a in r.ytdlp_calls if "--download-sections" not in a]
    assert len(source_dls) == 1


def test_fetch_ranged_raises_when_no_video_anywhere(tmp_path, monkeypatch):
    """If neither ranged nor native full download has video, surface the typed error."""
    r = _PathAwareRunner(video_paths=[])  # nothing ever has video
    dl = SegmentDownloader(r, Config(clamp_end_to_duration=False), tmp_path)
    _seed_output(monkeypatch, tmp_path, {
        "21.61-36.33": "V__21.61-36.33.mp4",
        "__source": "V__source.mp4",
    })

    with pytest.raises(NoVideoStreamError):
        dl.fetch_ranged(_clip(), lambda frac, status: None)

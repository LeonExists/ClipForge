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


# -- fetch_ranged guard ------------------------------------------------------

def test_fetch_ranged_rejects_audio_only(fake_runner, tmp_path, monkeypatch):
    """A resolved output with no video stream must raise NoVideoStreamError."""
    # yt-dlp "succeeds", ffprobe reports NO video stream (audio-only merge).
    r = fake_runner(per_tool={"ytdlp": {"returncode": 0}, "ffprobe": {"stdout": ""}})
    dl = SegmentDownloader(r, Config(clamp_end_to_duration=False), tmp_path)

    # Pretend yt-dlp produced a file so _resolve_output finds something.
    produced = tmp_path / "V__21.61-36.33.mp4"
    produced.write_bytes(b"\x00")
    monkeypatch.setattr(
        "clipforge.download.downloader.glob.glob", lambda pat: [str(produced)]
    )

    with pytest.raises(NoVideoStreamError):
        dl.fetch_ranged(_clip(), lambda frac, status: None)


def test_fetch_ranged_accepts_when_video_present(fake_runner, tmp_path, monkeypatch):
    r = fake_runner(per_tool={"ytdlp": {"returncode": 0}, "ffprobe": {"stdout": "video\n"}})
    dl = SegmentDownloader(r, Config(clamp_end_to_duration=False), tmp_path)

    produced = tmp_path / "V__21.61-36.33.mp4"
    produced.write_bytes(b"\x00")
    monkeypatch.setattr(
        "clipforge.download.downloader.glob.glob", lambda pat: [str(produced)]
    )

    seg = dl.fetch_ranged(_clip(), lambda frac, status: None)
    assert seg.path == str(produced)

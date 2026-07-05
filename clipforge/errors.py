"""Exception taxonomy + a pure classifier mapping yt-dlp stderr to typed errors.

The classifier is pure (string -> exception) so it is unit-tested directly against
canned stderr fixtures, with no network or subprocess.
"""

from __future__ import annotations


class ClipForgeError(Exception):
    """Base class for all ClipForge errors."""


class MissingDependencyError(ClipForgeError):
    """ffmpeg / ffprobe / yt-dlp not found on PATH (or faster-whisper not importable)."""


class InvalidRangeError(ClipForgeError):
    """Clip range is invalid (start < 0 or end <= start)."""


class DownloadError(ClipForgeError):
    """Base for download failures. Carries the source url and a stderr tail."""

    #: A user-facing template; subclasses override. `{url}` is substituted.
    user_message = "Download failed for {url}."

    def __init__(self, url: str = "", raw: str = ""):
        self.url = url
        self.raw = raw
        super().__init__(self.user_message.format(url=url))


class VideoUnavailableError(DownloadError):
    user_message = "This video is unavailable and can't be downloaded."


class PrivateVideoError(DownloadError):
    user_message = "This video is private. ClipForge can only process public videos."


class MembersOnlyError(DownloadError):
    user_message = "This is members-only content and can't be downloaded."


class AgeRestrictedError(DownloadError):
    user_message = "This video is age-restricted and requires sign-in; ClipForge can't fetch it."


class LoginRequiredError(DownloadError):
    user_message = (
        "YouTube is asking this machine to sign in / confirm it's not a bot. "
        "Try again later or configure cookies."
    )


class GeoBlockedError(DownloadError):
    user_message = "This video is geo-blocked in your region."


class VideoRemovedError(DownloadError):
    user_message = "This video has been removed or the channel was terminated."


class LiveNotStartedError(DownloadError):
    user_message = "This is a live/premiere that hasn't started; no downloadable video yet."


class FormatUnavailableError(DownloadError):
    user_message = "No compatible mp4 format was available for this video."


class NoVideoStreamError(DownloadError):
    user_message = (
        "The downloaded segment has no video track (audio only). This happens when "
        "yt-dlp's ffmpeg downloader can't seek the chosen source; retry, and if it "
        "persists lower the quality (max height) or change the format selector."
    )


class NetworkError(DownloadError):
    user_message = "Network problem reaching YouTube. Check your connection and retry."


class GenericDownloadError(DownloadError):
    user_message = "Download failed. See details below."


class EncodeError(ClipForgeError):
    """ffmpeg encode / probe failure."""


class TranscribeError(ClipForgeError):
    """Transcription backend failure."""


# Checked most-specific first. Each entry is (exception, [case-insensitive substrings]).
_SIGNATURES: list[tuple[type[DownloadError], list[str]]] = [
    (PrivateVideoError, [
        "private video", "this video is private",
        "sign in if you've been granted access",
    ]),
    (MembersOnlyError, ["available to this channel's members", "members-only"]),
    (AgeRestrictedError, [
        "confirm your age", "age-restricted", "inappropriate for some users",
    ]),
    (LoginRequiredError, [
        "sign in to confirm you're not a bot", "sign in to confirm", "login required",
    ]),
    (GeoBlockedError, [
        "not available in your country", "made this video available in your country",
        "blocked it in your country", "not available from your location", "geo restrict",
    ]),
    (VideoRemovedError, [
        "has been removed", "removed by the uploader",
        "account associated with this video has been terminated", "has been terminated",
    ]),
    (LiveNotStartedError, [
        "this live event will begin", "premieres in", "live stream recording is not available",
    ]),
    (FormatUnavailableError, ["requested format is not available"]),
    (VideoUnavailableError, [
        "video unavailable", "this video is unavailable", "content isn't available",
    ]),
    (NetworkError, [
        "unable to download webpage", "unable to download api page", "urlopen error",
        "getaddrinfo failed", "temporary failure in name resolution", "connection reset",
        "timed out", "read timed out", "http error 5",
    ]),
]


def classify_ytdlp_error(stderr: str, url: str = "") -> DownloadError:
    """Map a yt-dlp stderr blob to a typed DownloadError.

    Specific signatures are checked before generic ones (e.g. 'private' before
    'unavailable'). Falls back to GenericDownloadError carrying the stderr tail.
    """
    low = (stderr or "").lower()
    for exc, needles in _SIGNATURES:
        if any(n in low for n in needles):
            return exc(url=url, raw=stderr[-800:])
    return GenericDownloadError(url=url, raw=stderr[-800:])

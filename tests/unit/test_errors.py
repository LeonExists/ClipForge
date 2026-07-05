from clipforge.errors import (
    AgeRestrictedError,
    FormatUnavailableError,
    GenericDownloadError,
    GeoBlockedError,
    LoginRequiredError,
    NetworkError,
    PrivateVideoError,
    VideoRemovedError,
    VideoUnavailableError,
    classify_ytdlp_error,
)

URL = "https://youtu.be/abc"


def test_private():
    e = classify_ytdlp_error("ERROR: [youtube] abc: Private video. Sign in ...", URL)
    assert isinstance(e, PrivateVideoError)
    assert e.url == URL


def test_age_restricted():
    e = classify_ytdlp_error("ERROR: Sign in to confirm your age. This video may be inappropriate for some users.", URL)
    assert isinstance(e, AgeRestrictedError)


def test_login_required_bot_check():
    e = classify_ytdlp_error("ERROR: Sign in to confirm you're not a bot", URL)
    assert isinstance(e, LoginRequiredError)


def test_geo_blocked():
    e = classify_ytdlp_error("ERROR: The uploader has not made this video available in your country", URL)
    assert isinstance(e, GeoBlockedError)


def test_video_removed():
    e = classify_ytdlp_error("ERROR: Video has been removed by the uploader", URL)
    assert isinstance(e, VideoRemovedError)


def test_format_unavailable():
    e = classify_ytdlp_error("ERROR: Requested format is not available", URL)
    assert isinstance(e, FormatUnavailableError)


def test_video_unavailable():
    e = classify_ytdlp_error("ERROR: Video unavailable", URL)
    assert isinstance(e, VideoUnavailableError)


def test_network():
    e = classify_ytdlp_error("ERROR: Unable to download webpage: <urlopen error getaddrinfo failed>", URL)
    assert isinstance(e, NetworkError)


def test_generic_fallback():
    e = classify_ytdlp_error("ERROR: something totally unexpected happened", URL)
    assert isinstance(e, GenericDownloadError)
    assert "something totally unexpected" in e.raw


def test_private_precedence_over_unavailable():
    # A blob containing BOTH 'private' and 'unavailable' -> private wins (more specific).
    e = classify_ytdlp_error("This video is private. Video unavailable.", URL)
    assert isinstance(e, PrivateVideoError)

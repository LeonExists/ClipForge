"""Fast segment download lane (yt-dlp ranged fetch + videoId grouping)."""

from clipforge.download.downloader import SegmentDownloader, SegmentResult
from clipforge.download.plan import DownloadMode, DownloadPlan, plan_downloads, validate_range

__all__ = [
    "SegmentDownloader",
    "SegmentResult",
    "DownloadMode",
    "DownloadPlan",
    "plan_downloads",
    "validate_range",
]

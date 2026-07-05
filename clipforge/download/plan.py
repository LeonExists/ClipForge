"""Pure download planning: videoId grouping, range validation, ranged vs covering.

No I/O — decides *what* to fetch. The downloader executes the plan.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from clipforge.config import Config
from clipforge.errors import InvalidRangeError
from clipforge.models import Clip


class DownloadMode(str, Enum):
    RANGED = "ranged"      # one yt-dlp --download-sections per clip
    COVERING = "covering"  # one download of the min..max span, sliced locally


@dataclass
class DownloadPlan:
    videoId: str
    mode: DownloadMode
    clips: list[Clip]
    cover_start: float = 0.0
    cover_end: float = 0.0
    # padding applied to the covering span (so keyframe-aligned cuts have lead-in)
    pad: float = field(default=0.0)


def validate_range(clip: Clip) -> None:
    """Reject unrecoverable ranges. (end > duration is handled later by clamping.)"""
    if clip.start < 0:
        raise InvalidRangeError(f"clip {clip.id}: start ({clip.start}) must be >= 0")
    if clip.end <= clip.start:
        raise InvalidRangeError(
            f"clip {clip.id}: end ({clip.end}) must be greater than start ({clip.start})"
        )


def group_by_video_id(clips: list[Clip]) -> dict[str, list[Clip]]:
    """Group clips by videoId, preserving first-seen order of both ids and clips."""
    groups: dict[str, list[Clip]] = {}
    for c in clips:
        groups.setdefault(c.videoId, []).append(c)
    return groups


def plan_downloads(clips: list[Clip], cfg: Config, pad: float = 0.5) -> list[DownloadPlan]:
    """Plan per-videoId downloads.

    Default is RANGED (bandwidth-optimal, already avoids whole-video fetch). COVERING
    is chosen only for multi-clip groups that are tightly clustered/overlapping:
    when the covering span <= sum(clip spans) * overhead_factor OR the total gap
    (span - sum spans) <= gap_budget. Any single-clip group is always RANGED.
    """
    for c in clips:
        validate_range(c)

    plans: list[DownloadPlan] = []
    for vid, group in group_by_video_id(clips).items():
        if len(group) == 1 or cfg.download_grouping == "ranged":
            plans.append(DownloadPlan(vid, DownloadMode.RANGED, group))
            continue

        lo = min(c.start for c in group)
        hi = max(c.end for c in group)
        span = hi - lo
        total = _merged_span(group)  # dedupes overlapping clip intervals
        gaps = span - total

        if cfg.download_grouping == "covering":
            use_cover = True
        else:  # "auto"
            use_cover = (span <= total * cfg.covering_overhead_factor) or (
                gaps <= cfg.covering_gap_budget_sec
            )

        if use_cover:
            plans.append(
                DownloadPlan(
                    vid,
                    DownloadMode.COVERING,
                    group,
                    cover_start=max(0.0, lo - pad),
                    cover_end=hi + pad,
                    pad=pad,
                )
            )
        else:
            plans.append(DownloadPlan(vid, DownloadMode.RANGED, group))

    return plans


def _merged_span(clips: list[Clip]) -> float:
    """Total covered seconds after merging overlapping [start,end] intervals."""
    intervals = sorted((c.start, c.end) for c in clips)
    total = 0.0
    cur_lo, cur_hi = intervals[0]
    for lo, hi in intervals[1:]:
        if lo <= cur_hi:  # overlap or touch
            cur_hi = max(cur_hi, hi)
        else:
            total += cur_hi - cur_lo
            cur_lo, cur_hi = lo, hi
    total += cur_hi - cur_lo
    return total

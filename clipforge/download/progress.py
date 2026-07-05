"""Pure parser for yt-dlp progress lines emitted via our sentinel template."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

_SENTINEL = "__CFDL__\t"


@dataclass(frozen=True)
class DownloadProgress:
    fraction: Optional[float]  # 0..1, or None if unknown
    status: str
    eta: Optional[float]
    speed: Optional[float]


def _num(s: str) -> Optional[float]:
    if s in ("NA", "", "None"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_progress(line: str) -> Optional[DownloadProgress]:
    """Parse one yt-dlp progress line; return None for non-progress chatter.

    Fraction prefers downloaded/total, then downloaded/total_estimate, then the
    fragment_index/fragment_count fallback (DASH ranged fetches often lack a total).
    status=='finished' reserves the last ~1% for the merge/postprocess tail.
    """
    if _SENTINEL not in line:
        return None
    payload = line.split(_SENTINEL, 1)[1]
    parts = payload.split("\t")
    if len(parts) < 8:
        return None
    status, dl, tot, tot_est, frag_i, frag_n, eta, speed = parts[:8]

    dl_b = _num(dl)
    denom = _num(tot) or _num(tot_est)
    fraction: Optional[float] = None
    if dl_b is not None and denom:
        fraction = dl_b / denom
    elif _num(frag_n):
        fraction = (_num(frag_i) or 0.0) / _num(frag_n)  # type: ignore[operator]

    if status == "finished":
        fraction = 0.99  # merge/postprocess tail handled by caller

    if fraction is not None:
        fraction = max(0.0, min(1.0, fraction))

    return DownloadProgress(fraction=fraction, status=status, eta=_num(eta), speed=_num(speed))

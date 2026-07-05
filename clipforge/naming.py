"""Filesystem-safe output filenames: slug(title) + short-hash(id). Pure logic."""

from __future__ import annotations

import hashlib
import re
import unicodedata

# Windows reserved device names (case-insensitive, without extension).
_WIN_RESERVED = {
    "con", "prn", "aux", "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}


def slugify(title: str, max_len: int = 80) -> str:
    """Turn a title into a lowercase, ascii, filesystem-safe slug.

    NFKD-normalizes and strips accents, collapses runs of non-alphanumerics to a
    single hyphen, trims, caps length, and guards empty / Windows-reserved names.
    """
    normalized = unicodedata.normalize("NFKD", title or "")
    ascii_only = normalized.encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_only).strip("-").lower()
    s = s[:max_len].rstrip("-.")
    if not s or s in _WIN_RESERVED:
        s = f"clip-{s}".strip("-") if s else "clip"
    return s


def short_hash(clip_id: str, n: int = 8) -> str:
    """Deterministic short hex hash of the clip id (uniqueness across same titles)."""
    return hashlib.sha1(clip_id.encode("utf-8")).hexdigest()[:n]


def output_name(title: str, clip_id: str, ext: str = "mp4") -> str:
    """Filesystem-safe output filename: '<slug(title)>-<hash(id)>.<ext>'."""
    return f"{slugify(title)}-{short_hash(clip_id)}.{ext}"

"""Parse + validate the input JSON array into Clip objects. Pure logic."""

from __future__ import annotations

import json
from typing import Any

from clipforge.models import Clip

# Required string fields on each clip entry.
_REQUIRED_STR = ("id", "videoId", "url", "title")
# Required numeric fields.
_REQUIRED_NUM = ("start", "end")


class ClipParseError(ValueError):
    """Raised when the input JSON cannot be parsed into valid clips.

    `errors` holds structured per-entry problems for surfacing to the user.
    """

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors) if errors else "invalid clips JSON")


def parse_clips_text(text: str) -> list[Clip]:
    """Parse a JSON *string* into clips, raising ClipParseError on any problem."""
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as e:
        raise ClipParseError([f"invalid JSON: {e}"]) from e
    return parse_clips(raw)


def parse_clips(raw: Any) -> list[Clip]:
    """Validate an already-decoded JSON value into a list of Clip.

    Rules: top-level must be an array; each entry must have non-empty string
    id/videoId/url/title, finite numeric start/end with end > start, an optional
    string note; ids must be unique. Aggregates all problems into ClipParseError.
    """
    errors: list[str] = []
    if not isinstance(raw, list):
        raise ClipParseError(["top-level JSON must be an array of clips"])

    clips: list[Clip] = []
    seen_ids: set[str] = set()
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            errors.append(f"clip[{i}] must be an object")
            continue

        entry_errs: list[str] = []
        for f in _REQUIRED_STR:
            v = item.get(f)
            if not isinstance(v, str) or not v.strip():
                entry_errs.append(f"clip[{i}].{f} must be a non-empty string")

        nums: dict[str, float] = {}
        for f in _REQUIRED_NUM:
            v = item.get(f)
            # bool is an int subclass; reject it explicitly.
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                entry_errs.append(f"clip[{i}].{f} must be a number")
            else:
                fv = float(v)
                if fv != fv or fv in (float("inf"), float("-inf")):
                    entry_errs.append(f"clip[{i}].{f} must be finite")
                else:
                    nums[f] = fv

        if "start" in nums and "end" in nums:
            if nums["start"] < 0:
                entry_errs.append(f"clip[{i}].start must be >= 0")
            if nums["end"] <= nums["start"]:
                entry_errs.append(f"clip[{i}].end must be greater than start")

        note = item.get("note")
        if note is not None and not isinstance(note, str):
            entry_errs.append(f"clip[{i}].note must be a string if present")

        cid = item.get("id")
        if isinstance(cid, str) and cid.strip():
            if cid in seen_ids:
                entry_errs.append(f"clip[{i}].id duplicate: {cid!r}")
            seen_ids.add(cid)

        if entry_errs:
            errors.extend(entry_errs)
            continue

        clips.append(
            Clip(
                id=item["id"],
                videoId=item["videoId"],
                url=item["url"],
                title=item["title"],
                start=nums["start"],
                end=nums["end"],
                note=note,
                createdAt=item.get("createdAt"),
            )
        )

    if errors:
        raise ClipParseError(errors)
    return clips

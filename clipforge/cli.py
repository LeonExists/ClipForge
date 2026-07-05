"""Thin CLI wrapper — runs the same pipeline core headless.

    python -m clipforge sample.json --output-dir ./out
    python -m clipforge --sample --limit 1            # one clip end-to-end (vertical slice)
    python -m clipforge clips.json --reframe-mode blur_pad --whisper-model small.en
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from clipforge.batch import BatchRunner
from clipforge.config import Config
from clipforge.deps import preflight
from clipforge.errors import ClipForgeError
from clipforge.models import ProgressEvent, Stage
from clipforge.parsing import ClipParseError, parse_clips_text
from clipforge.pipeline import ClipProcessor
from clipforge.runner import Runner
from clipforge.transcribe.factory import get_transcriber

_SAMPLE = Path(__file__).resolve().parent / "assets" / "samples" / "sample.json"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="clipforge", description="YouTube clips -> captioned vertical shorts")
    p.add_argument("json", nargs="?", help="path to the clips JSON array")
    p.add_argument("--sample", action="store_true", help="use the bundled sample clips")
    p.add_argument("--clip-id", help="process only the clip with this id")
    p.add_argument("--limit", type=int, help="process at most N clips")
    p.add_argument("--output-dir", dest="output_dir", type=Path, help="where to write MP4s")
    p.add_argument("--tmp-dir", dest="tmp_dir", type=Path, help="scratch dir")
    p.add_argument("--reframe-mode", dest="reframe_mode", choices=["crop", "blur_pad"])
    p.add_argument("--whisper-model", dest="whisper_model")
    p.add_argument("--language", dest="language")
    p.add_argument("--caption-preset", dest="caption_preset")
    p.add_argument("--precise-cuts", dest="precise_cuts", action="store_true", default=None)
    p.add_argument("--no-precise-cuts", dest="precise_cuts", action="store_false", default=None)
    p.add_argument("--download-grouping", dest="download_grouping", choices=["ranged", "covering", "auto"])
    p.add_argument("--max-concurrency", dest="max_concurrency", type=int)
    p.add_argument("--encoder-override", dest="encoder_override")
    return p


def _load_clips(ns):
    if ns.sample or (ns.json is None):
        text = _SAMPLE.read_text(encoding="utf-8")
    else:
        text = Path(ns.json).read_text(encoding="utf-8")
    clips = parse_clips_text(text)
    if ns.clip_id:
        clips = [c for c in clips if c.id == ns.clip_id]
        if not clips:
            raise ClipForgeError(f"no clip with id {ns.clip_id!r}")
    if ns.limit is not None:
        clips = clips[: ns.limit]
    return clips


def _print_progress(ev: ProgressEvent) -> None:
    tag = ev.stage.value.upper()
    line = f"[{ev.clip_id[:24]:<24}] {tag:<10} {ev.pct:5.1f}%  {ev.message}"
    if ev.stage in (Stage.DONE, Stage.ERROR):
        print(line)
    else:
        # overwrite the current line for in-stage updates
        print(line, end="\r", flush=True)
        if ev.pct >= 100:
            print()


def main(argv: list[str] | None = None) -> int:
    ns = build_parser().parse_args(argv)
    try:
        cfg = Config.from_cli_args(ns)
        clips = _load_clips(ns)
    except ClipParseError as e:
        print("Input JSON invalid:", file=sys.stderr)
        for err in e.errors:
            print(f"  - {err}", file=sys.stderr)
        return 2
    except ClipForgeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2

    try:
        tools = preflight()
    except ClipForgeError as e:
        print(f"Dependency check failed:\n{e}", file=sys.stderr)
        return 3

    print(f"Loaded {len(clips)} clip(s). Loading whisper model '{cfg.whisper_model}'...")
    runner = Runner(tools)
    transcriber = get_transcriber(cfg)
    processor = ClipProcessor(runner, transcriber, cfg)
    batch = BatchRunner(processor)  # serial for CLI

    results = batch.run(clips, _print_progress)

    ok = [r for r in results if r.status == "done"]
    err = [r for r in results if r.status == "error"]
    print(f"\nDone: {len(ok)} succeeded, {len(err)} failed.")
    for r in ok:
        print(f"  OK  {r.output_path}  (encoder={r.encoder_used})")
    for r in err:
        print(f"  ERR {r.clip_id}: {r.error}", file=sys.stderr)
    return 0 if not err else 1


if __name__ == "__main__":
    raise SystemExit(main())

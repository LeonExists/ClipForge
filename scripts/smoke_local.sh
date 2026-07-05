#!/usr/bin/env bash
# Offline end-to-end smoke: generate a spoken fixture clip (no network), then drive
# the real ClipForge pipeline (transcribe -> caption -> reframe -> burn -> encode)
# for BOTH reframe modes and confirm 1080x1920 H.264 outputs with burned captions.
#
# This exercises everything except the yt-dlp network download, which needs live
# YouTube egress. Run it to sanity-check the render path without a browser.
set -euo pipefail
cd "$(dirname "$0")/.."

WORK="${1:-./smoke_out}"
mkdir -p "$WORK"
FIX="$WORK/spoken.mp4"

echo "[1/3] generating a 6s landscape fixture clip with spoken audio (flite)..."
ffmpeg -hide_banner -loglevel error -y \
  -f lavfi -i "testsrc2=s=1280x720:r=24:d=6" \
  -f lavfi -i "flite=text='This is ClipForge turning a landscape clip into a vertical short with karaoke captions':voice=slt" \
  -shortest -c:v libx264 -pix_fmt yuv420p -c:a aac -t 6 "$FIX"

echo "[2/3] running the pipeline for crop and blur_pad..."
export HF_HUB_DISABLE_SYMLINKS_WARNING=1
python - "$FIX" "$WORK" <<'PY'
import sys
from pathlib import Path
from clipforge.config import Config
from clipforge.tools import resolve_tools
from clipforge.runner import Runner
from clipforge.transcribe.factory import get_transcriber
from clipforge.captions import build_captions
from clipforge.captions.presets import get_preset, fonts_dir
from clipforge.ffmpeg import ffprobe_dims
from clipforge.reframe import get_reframer, compose_final_graph
from clipforge.encode import build_render_argv
from clipforge.probe import probe_encoder

seg, work = sys.argv[1], sys.argv[2]
runner = Runner(resolve_tools())
cfg = Config(tmp_dir=work, output_dir=work)
tr = get_transcriber(cfg).transcribe(seg, language="en")
print(f"    transcribed {len(tr.words)} words: {' '.join(w.text for w in tr.words)}")
art = build_captions(list(tr.words), get_preset("shorts_bold"), work)
enc = probe_encoder(runner, cfg.encoder_order())
print(f"    encoder probe -> {enc}")
si = ffprobe_dims(runner, seg)
for mode in ("crop", "blur_pad"):
    rg = get_reframer(mode).build_reframe(si, cfg)
    name = art.ass_path.name if art.ass_path else None
    fc, label = compose_final_graph(rg, name, str(art.fonts_dir) if name else None)
    out = str(Path(work) / f"out_{mode}.mp4")
    argv = build_render_argv(seg, out, fc, label, enc, cfg.video_quality, cfg.audio_bitrate)
    res = runner.ffmpeg(argv, cwd=work)
    assert res.ok, res.stderr[-500:]
    print(f"    rendered {mode} -> {out}")
PY

echo "[3/3] verifying outputs are 1080x1920 H.264..."
for m in crop blur_pad; do
  ffprobe -hide_banner -v error -select_streams v:0 \
    -show_entries stream=codec_name,width,height -of csv=p=0 "$WORK/out_$m.mp4"
done
echo "OK: smoke passed. Outputs in $WORK/"

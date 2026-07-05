# ClipForge

Turn a list of YouTube clip definitions into finished, captioned, **vertical (9:16, 1080×1920)**
short-form videos ready for YouTube Shorts / TikTok / Reels. Runs **fully locally** — no auth, no
cloud, no deployment. Ships as an importable Python pipeline, a headless CLI, and a small React web
app over the same core.

Per clip: **fast ranged download → transcribe → burned-in karaoke captions + vertical reframe →
1080×1920 H.264/AAC MP4**. Only the requested time range is fetched (a 3-second clip from a 1-hour
video downloads in seconds), and clips that share a `videoId` reuse one source.

![pipeline: download → transcribe → caption → render → done](https://img.shields.io/badge/pipeline-download→transcribe→caption→render→done-informational)

---

## What it does

- **Fast segment download** — `yt-dlp --download-sections "*{start}-{end}"`, preferring
  MP4/H.264 + M4A/AAC. Never downloads the whole video. `precise_cuts` (default on) adds
  `--force-keyframes-at-cuts` for frame-accurate boundaries. Clips sharing a `videoId` are grouped;
  `ranged` (default), `covering`, or `auto` strategies.
- **Vertical reframe** to 1080×1920 — `crop` (center-crop 16:9 → 9:16) or `blur_pad` (full clip
  centered over a blurred fill). Hardware-encodes when available (**runtime-probed**: NVENC →
  VideoToolbox → QSV → AMF, falling back to libx264), yuv420p, `+faststart`.
- **Transcription** — [faster-whisper](https://github.com/SYSTRAN/faster-whisper) with word
  timestamps. Default `small.en`; GPU (CUDA float16) if present, else CPU int8. Behind an interface
  so WhisperX can drop in later.
- **Karaoke captions** — a generated ASS subtitle burned in with ffmpeg. Large bold sans (bundled
  **Anton**), thick outline, lower-middle third, ~3 words at a time; the current word pops (scale +
  color). Style is a named preset object; alternate presets are a one-liner.
- **Output** — one 1080×1920 MP4 per clip, named `slug(title)-hash(id).mp4`. Per-clip download +
  "download all as ZIP" in the UI.

## Prerequisites

| Tool | Required | Notes |
|------|----------|-------|
| **Python** | ≥ 3.12 | backend + CLI |
| **Node.js** | ≥ 20 | web frontend only |
| **ffmpeg + ffprobe** | on `PATH` | cutting, reframe, caption burn, encode. No pip package — install via your OS (`winget install Gyan.FFmpeg`, `brew install ffmpeg`, `apt install ffmpeg`) |
| **yt-dlp** | on `PATH` (or pip) | installed as a pip dependency below; also works if already on `PATH` |

ClipForge fails fast with an actionable message if ffmpeg/yt-dlp are missing (and `GET /api/health`
reports tool status).

> **GPU note:** encoder selection is a *runtime probe* — ClipForge actually attempts a tiny encode
> with each candidate and keeps the first that works, rather than trusting `ffmpeg -encoders`. On a
> box that lists `h264_nvenc` but has no NVIDIA GPU, it correctly skips it and lands on QSV (Intel)
> or libx264.

## Quick start (Windows, one command)

If you're on Windows and just want to run it, use the bundled PowerShell scripts — they
install any missing prerequisites (Python 3.12+, Node, ffmpeg via `winget`), set up a
project-local `.venv`, build the UI, and launch the app on one port:

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
# then open http://localhost:8000  (opens automatically)
```

`start.ps1` is idempotent — re-run it any time. Options: `-Port 8080`, `-NoBrowser`,
`-SkipBuild`. It records anything it installs in `.clipforge-install.json`.

To remove everything ClipForge created (the `.venv`, `node_modules`, build output, working
dirs, the downloaded Whisper model, and **only** the system tools `start.ps1` itself
installed — never a pre-existing ffmpeg), run:

```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall.ps1
# flags: -KeepModels (keep the Whisper cache) · -KeepTools (keep system tools) · -Yes (no prompt)
```

Your source code is never touched. For manual setup, or on macOS/Linux, follow the steps below.

## Setup

### Backend (Python)

```bash
python -m venv .venv
# Windows (git-bash):   source .venv/Scripts/activate
# macOS/Linux:          source .venv/bin/activate

pip install -e ".[dev]"
```

If you don't have a CUDA GPU, install the CPU build of torch first (faster-whisper's ctranslate2
backend does not require torch, but if a torch dep is pulled in, prefer the CPU wheel):

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

The first transcription downloads the Whisper model (`small.en` ≈ a few hundred MB) from Hugging
Face and caches it; subsequent runs are fast.

### Frontend (React + Vite)

```bash
cd web
npm install
```

## Run it

### CLI (headless — no browser)

```bash
# One clip end-to-end from the bundled sample (the vertical-slice smoke path):
python -m clipforge --sample --limit 1 --output-dir ./out

# Full sample (3 clips, same videoId — fetched as 3 small ranged segments, not 3 full videos):
python -m clipforge clipforge/assets/samples/sample.json --output-dir ./out

# Options:
python -m clipforge clips.json \
  --output-dir ./out --tmp-dir ./tmp \
  --reframe-mode blur_pad \      # or crop (default)
  --whisper-model small.en \     # or small, medium, large-v3, ...
  --caption-preset shorts_bold \
  --no-precise-cuts \            # faster, keyframe-aligned cuts
  --download-grouping auto \     # ranged (default) | covering | auto
  --max-concurrency 3
```

### Web app

Two terminals:

```bash
# 1) backend on :8000
uvicorn server.app:app --port 8000

# 2) frontend dev server on :5173 (proxies /api and /events to :8000)
cd web && npm run dev
```

Open **http://localhost:5173**, drop or paste the JSON array, pick your settings, and hit **Forge**.
Watch per-clip progress (Download → Transcribe → Caption → Render → Done), preview each result, and
download individually or as a ZIP.

**Single-origin (production) alternative** — build the SPA and let FastAPI serve it:

```bash
cd web && npm run build      # -> web/dist
uvicorn server.app:app --port 8000
# open http://localhost:8000  (FastAPI serves the built SPA + the API on one origin)
```

## Input format

A JSON array exported from the Chrome extension. Each entry:

```json
{
  "createdAt": "2026-07-03T14:48:23.279Z",
  "end": 36.33,
  "id": "Q260EqSF5aA-1783090103279-3cj9fk",
  "note": "",
  "start": 21.61,
  "title": "Stable Ronaldo's Funniest Moments!",
  "url": "https://www.youtube.com/watch?v=Q260EqSF5aA",
  "videoId": "Q260EqSF5aA"
}
```

Used fields: `url`, `videoId`, `start` (float sec), `end` (float sec), `title`, `id` (unique),
`note` (optional). Clips sharing a `videoId` are handled efficiently.

## Configuration

All knobs live in one `clipforge.config.Config` (loadable from CLI args and the web request body).
Highlights: `precise_cuts`, `download_grouping`, `reframe_mode`, `blur_sigma`, `encoder_candidates`,
`video_quality`, `whisper_model`, `language`, `caption_preset`, `max_concurrency`, `output_dir`,
`tmp_dir`. Caption presets (`clipforge/captions/presets.py`) bundle font, colors, position,
words-per-group, and animation (`none` | `karaoke` | `pop` | `both`).

## Architecture

```
clipforge/            importable pipeline core (FastAPI-independent) + CLI
  runner.py           the ONLY subprocess boundary; every lane builds pure argv and passes it here
  download/           yt-dlp ranged fetch, videoId grouping (ranged/covering/auto), progress parsing
  transcribe/         Transcriber interface + faster-whisper backend (WhisperX seam)
  captions/           pure word-grouping + karaoke ASS generation + preset registry
  reframe.py          crop / blur_pad filtergraphs + AutoReframer seam; compose_final_graph()
  encode.py, probe.py runtime encoder probe + per-encoder flags; single combined render pass
  pipeline.py         ClipProcessor: one clip end-to-end, emits stage progress via a callback
  batch.py            videoId grouping ABOVE the processor; shared-source dedupe
  cli.py              thin argparse wrapper -> same core, headless
server/               FastAPI job layer: bounded ThreadPoolExecutor, in-memory store, SSE + polling
web/                  Vite + React + TS SPA (drop/paste JSON, config, live progress, preview, ZIP)
tests/unit/           pytest for the pure logic (no network, shell-out mocked)
scripts/smoke_local.sh  offline end-to-end (generates a spoken fixture via ffmpeg flite)
```

The pipeline runs one combined ffmpeg pass — reframe filtergraph + ASS caption burn + encode — so
there's no intermediate re-encode. Word timings are relative to the cut clip (t=0 = clip start), so
captions line up with the reframed output without any offset math.

## Testing

Pure logic is unit-tested; the yt-dlp/ffmpeg/whisper shell-out layer is mocked (a `fake_runner`
fixture records argv) or exercised only by the smoke script.

```bash
pytest -q                       # backend: 131 tests (parsing, grouping, ASS/karaoke, slugging, probe, config, ...)
cd web && npm test              # frontend: 30 tests (JSON validation, grouping, progress reducer, formatting)
bash scripts/smoke_local.sh     # offline end-to-end: fixture clip -> both reframe modes -> 1080x1920 outputs
```

## Roadmap / seams (not built in v1)

- **auto_reframe** — face/subject tracking with a smoothed crop path (Reframer registry seam exists).
- **WhisperX** — forced alignment for tighter word timing (Transcriber interface seam exists).
- **Cookies** — for age/login-gated videos.

## License

Bundled font **Anton** is under the SIL Open Font License (see
`clipforge/assets/fonts/OFL.txt`).

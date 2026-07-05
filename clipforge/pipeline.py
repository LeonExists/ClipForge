"""Framework-free per-clip pipeline core.

ClipProcessor.process() drives one clip: download -> transcribe -> caption ->
reframe+caption-burn+encode (ONE ffmpeg pass) -> output. Progress is emitted through
a callback so both the CLI and the web layer consume the identical engine.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from clipforge.captions import build_captions
from clipforge.captions.presets import get_preset
from clipforge.config import Config
from clipforge.download.downloader import SegmentDownloader, SegmentResult
from clipforge.download.plan import DownloadMode, DownloadPlan
from clipforge.encode import build_render_argv
from clipforge.ffmpeg import ffprobe_dims
from clipforge.models import Clip, ClipResult, ProgressCallback, ProgressEvent, Stage
from clipforge.naming import output_name
from clipforge.probe import probe_encoder
from clipforge.reframe import compose_final_graph, get_reframer
from clipforge.runner import Runner
from clipforge.transcribe.base import Transcriber


class _Emit:
    def __init__(self, clip_id: str, cb: ProgressCallback):
        self.clip_id = clip_id
        self.cb = cb

    def __call__(self, stage: Stage, pct: float, msg: str = "", status: str = "running") -> None:
        self.cb(ProgressEvent(self.clip_id, stage, pct, msg, status))


class ClipProcessor:
    """Processes a single clip end-to-end. Reusable across clips (holds warm model)."""

    def __init__(self, runner: Runner, transcriber: Transcriber, cfg: Config):
        self.runner = runner
        self.transcriber = transcriber
        self.cfg = cfg
        self.downloader = SegmentDownloader(runner, cfg, cfg.tmp_dir)

    def process(
        self,
        clip: Clip,
        on_progress: ProgressCallback,
        *,
        plan: Optional[DownloadPlan] = None,
        covering_path: Optional[str] = None,
    ) -> ClipResult:
        emit = _Emit(clip.id, on_progress)
        timings: dict = {}
        t0 = time.perf_counter()
        try:
            # 1. DOWNLOAD (or slice from a shared covering source)
            emit(Stage.DOWNLOAD, 0, "fetching segment")
            seg = self._acquire_segment(clip, emit, plan, covering_path)
            emit(Stage.DOWNLOAD, 100, "segment ready", status="running")
            timings["download"] = time.perf_counter() - t0

            # 2. TRANSCRIBE the cut clip (t=0 = clip start)
            t1 = time.perf_counter()
            emit(Stage.TRANSCRIBE, 0, "transcribing")
            transcript = self.transcriber.transcribe(seg.path, language=self.cfg.language)
            emit(Stage.TRANSCRIBE, 100, f"{len(transcript.words)} words", status="running")
            timings["transcribe"] = time.perf_counter() - t1

            # 3. CAPTION (pure, fast): build the .ass file
            t2 = time.perf_counter()
            emit(Stage.CAPTION, 0, "rendering captions")
            preset = get_preset(self.cfg.caption_preset)
            artifacts = build_captions(list(transcript.words), preset, self.cfg.tmp_dir)
            emit(Stage.CAPTION, 100, "captions ready", status="running")
            timings["caption"] = time.perf_counter() - t2

            # 4. RENDER: reframe + caption burn + encode in ONE ffmpeg pass
            t3 = time.perf_counter()
            emit(Stage.RENDER, 0, "reframe + encode")
            out_path, encoder = self._render(clip, seg, artifacts, emit)
            timings["render"] = time.perf_counter() - t3

            emit(Stage.DONE, 100, "done", status="done")
            return ClipResult(
                clip_id=clip.id,
                title=clip.title,
                status="done",
                output_path=out_path,
                duration=clip.duration,
                encoder_used=encoder,
                whisper_device=self.cfg.whisper_device,
                timings=timings,
            )
        except Exception as e:
            emit(Stage.ERROR, 0, str(e), status="error")
            return ClipResult(clip.id, clip.title, "error", error=str(e), timings=timings)

    # -- stages --------------------------------------------------------------

    def _acquire_segment(self, clip, emit, plan, covering_path) -> SegmentResult:
        if plan is not None and plan.mode == DownloadMode.COVERING and covering_path:
            encoder = self._encoder()
            return self.downloader.slice_from_covering(covering_path, plan, clip, encoder)

        def dl_progress(frac: float, status: str) -> None:
            emit(Stage.DOWNLOAD, frac * 100.0, status)

        # Pass the encoder so the native-full-download fallback can do a precise
        # local re-encode cut (matches slice_from_covering's behaviour).
        encoder = self._encoder() if self.cfg.precise_cuts else None
        return self.downloader.fetch_ranged(clip, dl_progress, encoder)

    def _render(self, clip: Clip, seg: SegmentResult, artifacts, emit) -> tuple[Path, str]:
        src_info = ffprobe_dims(self.runner, seg.path)
        reframer = get_reframer(self.cfg.reframe_mode)
        rg = reframer.build_reframe(src_info, self.cfg)

        ass_name = artifacts.ass_path.name if artifacts.ass_path else None
        fc, out_label = compose_final_graph(
            rg,
            ass_name,
            str(artifacts.fonts_dir) if ass_name else None,
            use_bare_ass_name=True,
        )

        encoder = self._encoder()
        out_dir = Path(self.cfg.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / output_name(clip.title, clip.id)

        argv = build_render_argv(
            src=str(Path(seg.path).resolve()),
            dst=str(out_path.resolve()),
            filter_complex=fc,
            map_label=out_label,
            encoder=encoder,
            quality=self.cfg.video_quality,
            audio_bitrate=self.cfg.audio_bitrate,
        )
        # Run with cwd=tmp_dir so the bare captions.ass filename resolves (avoids
        # Windows drive-colon/space escaping inside the filtergraph).
        cwd = str(Path(self.cfg.tmp_dir).resolve())
        res = self.runner.ffmpeg(argv, cwd=cwd)
        if not res.ok:
            # qsv can pass a probe yet regress on a real graph; retry once on libx264.
            if encoder != "libx264":
                emit(Stage.RENDER, 50, f"{encoder} failed, retrying with libx264")
                argv_fb = build_render_argv(
                    src=str(Path(seg.path).resolve()),
                    dst=str(out_path.resolve()),
                    filter_complex=fc,
                    map_label=out_label,
                    encoder="libx264",
                    quality=self.cfg.video_quality,
                    audio_bitrate=self.cfg.audio_bitrate,
                )
                res = self.runner.ffmpeg(argv_fb, cwd=cwd)
                encoder = "libx264"
            if not res.ok:
                from clipforge.errors import EncodeError

                raise EncodeError(f"render failed: {res.stderr.strip()[-500:]}")
        emit(Stage.RENDER, 100, "rendered", status="running")
        return out_path, encoder

    def _encoder(self) -> str:
        if self.cfg.encoder_override:
            return self.cfg.encoder_override
        return probe_encoder(
            self.runner,
            self.cfg.encoder_order(),
            self.cfg.target_width,
            self.cfg.target_height,
        )

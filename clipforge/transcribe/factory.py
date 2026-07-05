"""Transcriber factory — the single place the WhisperX seam opens."""

from __future__ import annotations

import os

from clipforge.config import Config
from clipforge.transcribe.base import Transcriber


def get_transcriber(cfg: Config) -> Transcriber:
    backend = cfg.transcriber_backend
    if backend == "faster_whisper":
        from clipforge.transcribe.faster_whisper import FasterWhisperTranscriber

        cpu_threads = cfg.whisper_cpu_threads
        if cpu_threads == 0:
            cores = os.cpu_count() or 1
            cpu_threads = max(1, cores // max(1, cfg.max_concurrency))

        return FasterWhisperTranscriber(
            model_size=cfg.whisper_model,
            device=cfg.whisper_device,
            compute_type=cfg.whisper_compute_type,
            beam_size=cfg.whisper_beam_size,
            vad_filter=cfg.whisper_vad_filter,
            condition_on_previous_text=cfg.whisper_condition_on_previous_text,
            cpu_threads=cpu_threads,
        )
    if backend == "whisperx":  # future: forced-alignment upgrade behind the same interface
        raise NotImplementedError("whisperx backend not built yet (v2)")
    raise ValueError(f"unknown transcriber_backend {backend!r}")

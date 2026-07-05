"""faster-whisper transcriber. The only module importing faster_whisper (mocked in tests)."""

from __future__ import annotations

import threading
from pathlib import Path

from clipforge.config import KNOWN_WHISPER_MODELS
from clipforge.errors import TranscribeError
from clipforge.probe import probe_device_compute
from clipforge.transcribe.base import Transcriber, Transcript
from clipforge.transcribe.mapping import build_transcript


class FasterWhisperTranscriber(Transcriber):
    def __init__(
        self,
        model_size: str = "small.en",
        device: str = "auto",
        compute_type: str = "auto",
        beam_size: int = 5,
        vad_filter: bool = True,
        condition_on_previous_text: bool = False,
        cpu_threads: int = 0,
        download_root: str | None = None,
        local_files_only: bool = False,
    ):
        if model_size not in KNOWN_WHISPER_MODELS:
            raise ValueError(f"unknown whisper_model {model_size!r}")
        self.model_size = model_size
        self.beam_size = beam_size
        self.vad_filter = vad_filter
        self.condition_on_previous_text = condition_on_previous_text

        from faster_whisper import WhisperModel

        dev, comp = probe_device_compute(device, compute_type)
        try:
            self._model = WhisperModel(
                model_size, device=dev, compute_type=comp,
                cpu_threads=cpu_threads, download_root=download_root,
                local_files_only=local_files_only,
            )
        except Exception:
            if dev == "cuda":  # advertised CUDA but float16/cuDNN unusable -> CPU int8
                self._model = WhisperModel(
                    model_size, device="cpu", compute_type="int8",
                    cpu_threads=cpu_threads, download_root=download_root,
                    local_files_only=local_files_only,
                )
            else:
                raise
        self._lock = threading.Lock()  # transcribe() is not concurrency-safe on one model

    def transcribe(self, media_path: str | Path, language: str | None = None) -> Transcript:
        if self.model_size.endswith(".en"):
            if language not in (None, "en"):
                raise ValueError(f"{self.model_size} is English-only (got language={language!r})")
            language = "en"
        try:
            with self._lock:
                segments, info = self._model.transcribe(
                    str(Path(media_path)),
                    language=language,
                    word_timestamps=True,
                    beam_size=self.beam_size,
                    vad_filter=self.vad_filter,
                    condition_on_previous_text=self.condition_on_previous_text,
                )
                return build_transcript(segments, info)
        except ValueError:
            raise
        except Exception as e:  # pragma: no cover - backend-specific
            raise TranscribeError(f"transcription failed for {media_path}: {e}") from e

"""Single consolidated Config spanning every lane's flags.

Loadable from CLI args (argparse Namespace) and from the web request body (reused
directly as a pydantic model). This is the one authoritative knob surface.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

# Default hardware-encoder probe order. libx264 is ALWAYS appended last as the
# universal fallback (see encoder_order()); do not put it here.
DEFAULT_ENCODER_ORDER = ["h264_nvenc", "h264_videotoolbox", "h264_qsv", "h264_amf"]

# Known faster-whisper model ids.
KNOWN_WHISPER_MODELS = {
    "tiny", "tiny.en", "base", "base.en", "small", "small.en",
    "medium", "medium.en", "large-v3",
}


class Config(BaseModel):
    """All ClipForge configuration in one place."""

    # --- download ---
    precise_cuts: bool = True
    download_grouping: Literal["ranged", "covering", "auto"] = "ranged"
    download_max_height: int = 1080
    # Ranged (--download-sections) format ladder. --download-sections routes yt-dlp
    # to its ffmpeg downloader, which byte-seeks the source. Fragmented DASH
    # (YouTube's default >=720p mp4) is NOT byte-seekable — ffmpeg reads the whole
    # remote file, which stalls AND drops the video track (audio-only output). HLS
    # (m3u8_native) is segment-addressed, so ffmpeg fetches only the in-range
    # segments: truly ranged, fast, full-res H.264. But YouTube only serves HLS on
    # ~half of requests here; when it's absent this ladder would fall to progressive
    # 360p, so instead of degrading we fall back to a NATIVE full download (see
    # download_full_format) which the caller cuts locally. `None` => derive from
    # download_max_height via download.args.ranged_format_selector.
    download_format: Optional[str] = None
    # Native full-download selector (NO --download-sections => native downloader,
    # which does not stall on fragmented DASH). Used when the ranged HLS attempt
    # yields no usable video. Prefers H.264 (cheaper to decode than AV1) capped at
    # download_max_height. `None` => derive via download.args.full_format_selector.
    download_full_format: Optional[str] = None
    covering_overhead_factor: float = 1.5
    covering_gap_budget_sec: float = 30.0
    concurrent_fragments: int = 4
    download_retries: int = 3
    socket_timeout_sec: int = 30
    clamp_end_to_duration: bool = True

    # --- reframe / encode ---
    reframe_mode: Literal["crop", "blur_pad"] = "crop"
    target_width: int = 1080
    target_height: int = 1920
    blur_sigma: int = 20
    encoder_candidates: list[str] = Field(default_factory=lambda: list(DEFAULT_ENCODER_ORDER))
    encoder_override: Optional[str] = None
    video_quality: int = 23
    audio_bitrate: str = "160k"

    # --- transcribe ---
    whisper_model: str = "small.en"
    language: Optional[str] = None
    whisper_device: Literal["auto", "cpu", "cuda"] = "auto"
    whisper_compute_type: Literal["auto", "int8", "float16", "int8_float16", "float32"] = "auto"
    whisper_beam_size: int = 5
    whisper_vad_filter: bool = True
    whisper_condition_on_previous_text: bool = False
    whisper_cpu_threads: int = 0  # 0 = auto (cpu_count // max_concurrency)
    transcriber_backend: Literal["faster_whisper", "whisperx"] = "faster_whisper"

    # --- captions ---
    caption_preset: str = "shorts_bold"

    # --- runtime / io ---
    max_concurrency: int = 3
    output_dir: Path = Path("./out")
    tmp_dir: Path = Path("./tmp")
    keep_tmp: bool = False

    @field_validator("whisper_model")
    @classmethod
    def _validate_model(cls, v: str) -> str:
        if v not in KNOWN_WHISPER_MODELS:
            raise ValueError(
                f"unknown whisper_model {v!r}; known: {sorted(KNOWN_WHISPER_MODELS)}"
            )
        return v

    @field_validator("max_concurrency")
    @classmethod
    def _validate_concurrency(cls, v: int) -> int:
        if v < 1:
            raise ValueError("max_concurrency must be >= 1")
        return v

    def encoder_order(self) -> list[str]:
        """Probe order with libx264 guaranteed exactly once as the final fallback."""
        order = [e for e in self.encoder_candidates if e != "libx264"]
        return order + ["libx264"]

    @classmethod
    def from_cli_args(cls, ns) -> "Config":
        """Build a Config from an argparse Namespace, honoring only set (non-None) flags."""
        overrides = {
            k: v for k, v in vars(ns).items()
            if k in cls.model_fields and v is not None
        }
        return cls(**overrides)


class JobRequest(BaseModel):
    """Web request body: raw clip dicts + a Config. Clips are validated by parse_clips."""

    clips: list[dict]
    config: Config = Field(default_factory=Config)

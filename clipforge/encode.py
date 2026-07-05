"""Encode argv assembly: reframe filtergraph + probed encoder -> final MP4.

Per-encoder rate-control flags differ (cq vs global_quality vs crf); one
video_quality int maps to each via a table. Output is always H.264 + AAC, yuv420p,
+faststart.
"""

from __future__ import annotations

from clipforge.errors import EncodeError


def _encoder_flags(encoder: str, quality: int) -> list[str]:
    q = str(quality)
    table = {
        "h264_nvenc": ["-c:v", "h264_nvenc", "-preset", "p5", "-tune", "hq",
                       "-rc", "vbr", "-cq", q, "-b:v", "0"],
        "h264_videotoolbox": ["-c:v", "h264_videotoolbox", "-b:v", "6M"],
        "h264_qsv": ["-c:v", "h264_qsv", "-global_quality", q, "-preset", "veryfast"],
        "h264_amf": ["-c:v", "h264_amf", "-rc", "cqp", "-qp_i", q, "-qp_p", q],
        # libx264 uses a lower crf number for equivalent quality.
        "libx264": ["-c:v", "libx264", "-crf", str(max(0, quality - 4)),
                    "-preset", "veryfast", "-pix_fmt", "yuv420p"],
    }
    try:
        return table[encoder]
    except KeyError:
        raise EncodeError(f"unknown encoder {encoder!r}")


def build_render_argv(
    src: str,
    dst: str,
    filter_complex: str,
    map_label: str,
    encoder: str,
    quality: int,
    audio_bitrate: str = "160k",
) -> list[str]:
    """Argv (without ffmpeg prefix) for the single combined reframe+caption+encode pass.

    Note: when captions are burned by bare filename, run ffmpeg with cwd=<tmp dir>.
    """
    return [
        "-y",
        "-i", src,
        "-filter_complex", filter_complex,
        "-map", f"[{map_label}]",
        "-map", "0:a?",
        *_encoder_flags(encoder, quality),
        "-c:a", "aac",
        "-b:a", audio_bitrate,
        "-movflags", "+faststart",
        dst,
    ]

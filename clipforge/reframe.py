"""Vertical reframe to 1080x1920 as ffmpeg filtergraph fragments.

A Reframer produces a `ReframeGraph` (a list of filter_complex chains ending in a
labeled pad). The compositor splices the caption `ass` filter onto that pad, so the
whole reframe + caption burn + encode happens in ONE ffmpeg pass.

Both graphs are VERIFIED on the target box to produce exactly 1080x1920, SAR 1:1.
A future AutoReframer registers itself here and returns the same ReframeGraph
contract — no changes needed in encode/compose.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from clipforge.config import Config
from clipforge.ffmpeg import SourceInfo, escape_filter_path


@dataclass
class ReframeGraph:
    chains: list[str]  # filter_complex fragments
    out_label: str     # the pad the compositor consumes (e.g. "vr")


class Reframer(ABC):
    mode: str

    @abstractmethod
    def build_reframe(self, src: SourceInfo, cfg: Config) -> ReframeGraph:
        ...


REFRAMERS: dict[str, type[Reframer]] = {}


def register(cls: type[Reframer]) -> type[Reframer]:
    REFRAMERS[cls.mode] = cls
    return cls


def get_reframer(mode: str) -> Reframer:
    try:
        return REFRAMERS[mode]()
    except KeyError:
        raise ValueError(f"unknown reframe_mode {mode!r}; available: {sorted(REFRAMERS)}")


@register
class CropReframer(Reframer):
    """Center-crop to 9:16 then scale. The paired min() expressions correctly
    no-op the crop for already-portrait sources instead of over-cropping."""

    mode = "crop"

    def build_reframe(self, src: SourceInfo, cfg: Config) -> ReframeGraph:
        w, h = cfg.target_width, cfg.target_height
        chain = (
            f"[0:v]crop='min(iw,ih*{w}/{h})':'min(ih,iw*{h}/{w})',"
            f"scale={w}:{h},setsar=1[vr]"
        )
        return ReframeGraph([chain], "vr")


@register
class BlurPadReframer(Reframer):
    """Full clip centered over a blurred, scaled copy that fills the 9:16 canvas."""

    mode = "blur_pad"

    def build_reframe(self, src: SourceInfo, cfg: Config) -> ReframeGraph:
        w, h = cfg.target_width, cfg.target_height
        sigma = cfg.blur_sigma
        chains = [
            "[0:v]split=2[bg][fg]",
            f"[bg]scale={w}:{h}:force_original_aspect_ratio=increase,"
            f"crop={w}:{h},gblur=sigma={sigma}[bgb]",
            f"[fg]scale={w}:{h}:force_original_aspect_ratio=decrease[fgs]",
            "[bgb][fgs]overlay=(W-w)/2:(H-h)/2,setsar=1[vr]",
        ]
        return ReframeGraph(chains, "vr")


def compose_final_graph(
    rg: ReframeGraph,
    ass_path: str | None,
    fontsdir: str | None,
    *,
    use_bare_ass_name: bool = True,
) -> tuple[str, str]:
    """Splice the caption burn (if any) onto the reframe pad; return (filter_complex, out_label).

    When `use_bare_ass_name` (default), the .ass is referenced by bare filename and
    ffmpeg is expected to run with cwd=<tmp dir>, sidestepping Windows path escaping.
    fontsdir still needs escaping since it points at the packaged assets dir.
    """
    chains = list(rg.chains)
    if ass_path:
        name = ass_path if use_bare_ass_name else escape_filter_path(ass_path)
        opt = f"ass='{name}'"
        if fontsdir:
            opt += f":fontsdir='{escape_filter_path(fontsdir)}'"
        chains.append(f"[{rg.out_label}]{opt},format=yuv420p[vout]")
    else:
        chains.append(f"[{rg.out_label}]format=yuv420p[vout]")
    return ";".join(chains), "vout"

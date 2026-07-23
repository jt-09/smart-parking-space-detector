"""Factory helpers for constructing frame sources from config-like specs."""

from __future__ import annotations

from pathlib import Path

from smart_parking.sources.base import FrameSource, ReconnectPolicy
from smart_parking.sources.opencv_source import OpenCVFrameSource
from smart_parking.sources.synthetic import SyntheticFrameSource


def create_frame_source(
    source: str | int,
    *,
    source_id: str | None = None,
    reconnect: ReconnectPolicy | None = None,
    synthetic_frames: int = 30,
) -> FrameSource:
    """Build a frame source from a path, webcam index, URI, or ``synthetic:`` token.

    Examples:
        ``data/clip.mp4``, ``0``, ``rtsp://user:pass@host/stream``, ``synthetic``
    """
    if isinstance(source, int):
        return OpenCVFrameSource(source, source_id=source_id, reconnect=reconnect)

    token = source.strip().lower()
    if token in {"synthetic", "synthetic:", "synth"} or token.startswith("synthetic:"):
        width, height, count = 64, 48, synthetic_frames
        if ":" in source and not token.startswith("synthetic://"):
            # synthetic:WxH:N
            parts = source.split(":")
            if len(parts) >= 3:
                try:
                    width = int(parts[1])
                    height = int(parts[2])
                except ValueError:
                    width, height = 64, 48
            if len(parts) >= 4:
                try:
                    count = int(parts[3])
                except ValueError:
                    count = synthetic_frames
        return SyntheticFrameSource(
            source_id=source_id or "synthetic",
            width=width,
            height=height,
            frame_count=count,
            moving_rectangle=True,
        )

    return OpenCVFrameSource(
        source,
        source_id=source_id or Path(source).name,
        reconnect=reconnect,
    )

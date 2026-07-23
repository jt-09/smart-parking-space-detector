"""Frame ingestion adapters (image, video, webcam, stream, synthetic)."""

from smart_parking.sources.base import (
    Frame,
    FrameMetadata,
    FrameSource,
    FrameSourceClosed,
    FrameSourceEOF,
    FrameSourceError,
    ImageArray,
    ReconnectPolicy,
    redact_source_uri,
)
from smart_parking.sources.synthetic import SyntheticFrameSource

__all__ = [
    "Frame",
    "FrameMetadata",
    "FrameSource",
    "FrameSourceClosed",
    "FrameSourceEOF",
    "FrameSourceError",
    "ImageArray",
    "ReconnectPolicy",
    "SyntheticFrameSource",
    "redact_source_uri",
]

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
from smart_parking.sources.factory import create_frame_source
from smart_parking.sources.opencv_source import OpenCVFrameSource
from smart_parking.sources.synthetic import SyntheticFrameSource

__all__ = [
    "Frame",
    "FrameMetadata",
    "FrameSource",
    "FrameSourceClosed",
    "FrameSourceEOF",
    "FrameSourceError",
    "ImageArray",
    "OpenCVFrameSource",
    "ReconnectPolicy",
    "SyntheticFrameSource",
    "create_frame_source",
    "redact_source_uri",
]

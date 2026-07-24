"""Vehicle detection adapters (protocol + backends)."""

from smart_parking.detection.base import Detector
from smart_parking.detection.models import BoundingBox, Detection, DetectionBatch

__all__ = [
    "BoundingBox",
    "Detection",
    "DetectionBatch",
    "Detector",
]

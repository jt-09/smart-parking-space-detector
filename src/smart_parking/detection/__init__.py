"""Vehicle detection adapters (protocol + backends)."""

from smart_parking.detection.base import Detector
from smart_parking.detection.fake import FakeDetector, default_fake_detections
from smart_parking.detection.models import BoundingBox, Detection, DetectionBatch
from smart_parking.detection.ultralytics_detector import (
    DEFAULT_ALLOWED_CLASSES,
    UltralyticsDetector,
    weights_available,
)

__all__ = [
    "DEFAULT_ALLOWED_CLASSES",
    "BoundingBox",
    "Detection",
    "DetectionBatch",
    "Detector",
    "FakeDetector",
    "UltralyticsDetector",
    "default_fake_detections",
    "weights_available",
]

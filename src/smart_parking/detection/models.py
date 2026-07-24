"""Thin detection result types built on domain Detection / BoundingBox."""

from __future__ import annotations

from dataclasses import dataclass

from smart_parking.domain.parking import BoundingBox, Detection

__all__ = [
    "BoundingBox",
    "Detection",
    "DetectionBatch",
]


@dataclass(frozen=True, slots=True)
class DetectionBatch:
    """Normalized detections for a single frame, plus backend provenance."""

    detections: tuple[Detection, ...]
    model_name: str
    device: str
    frame_index: int | None = None
    inference_ms: float | None = None

    def __post_init__(self) -> None:
        if not self.model_name.strip():
            raise ValueError("model_name must be a non-empty string.")
        if not self.device.strip():
            raise ValueError("device must be a non-empty string.")
        if self.inference_ms is not None and self.inference_ms < 0.0:
            raise ValueError(f"inference_ms must be >= 0, got {self.inference_ms}.")

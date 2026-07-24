"""Detector protocol — domain and pipeline depend on this, not Ultralytics."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np
from numpy.typing import NDArray

from smart_parking.detection.models import DetectionBatch

# BGR uint8 image as produced by frame sources / OpenCV adapters.
ImageArray = NDArray[np.uint8]


@runtime_checkable
class Detector(Protocol):
    """Backend-agnostic vehicle detector interface.

    Implementations return domain ``Detection`` objects (via ``DetectionBatch``).
    Callers must not depend on Ultralytics or other vendor types.
    """

    @property
    def model_name(self) -> str:
        """Configured model identifier or path (for logs and provenance)."""

    @property
    def device(self) -> str:
        """Inference device string (for example ``cpu`` or ``cuda:0``)."""

    @property
    def tracking_enabled(self) -> bool:
        """Whether this detector emits persistent ``track_id`` values when available."""

    def detect(
        self,
        image: ImageArray,
        *,
        frame_index: int | None = None,
    ) -> DetectionBatch:
        """Run detection (and optional tracking) on a BGR ``HxWx3`` frame."""

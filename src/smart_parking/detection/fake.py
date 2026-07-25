"""Deterministic fake detector for tests (no network or weights)."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

import numpy as np

from smart_parking.detection.base import ImageArray
from smart_parking.detection.models import BoundingBox, Detection, DetectionBatch

DetectionScript = Mapping[int, Sequence[Detection]] | Callable[[int | None], Sequence[Detection]]


class FakeDetector:
    """Return configured detections without loading a real model.

    Useful for contract tests and pipeline fixtures. Boxes may be absolute
    pixel coordinates or fractions of frame width/height when ``normalized``
    is True.

    When ``script`` is provided, per-frame detections override the default
    list (mapping keyed by frame index, or a callable receiving frame_index).
    """

    def __init__(
        self,
        detections: Sequence[Detection] | None = None,
        *,
        model_name: str = "fake",
        device: str = "cpu",
        tracking_enabled: bool = True,
        normalized: bool = False,
        inference_ms: float = 0.0,
        script: DetectionScript | None = None,
    ) -> None:
        self._detections = tuple(detections or ())
        self._model_name = model_name
        self._device = device
        self._tracking_enabled = tracking_enabled
        self._normalized = normalized
        self._inference_ms = inference_ms
        self._script = script

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def device(self) -> str:
        return self._device

    @property
    def tracking_enabled(self) -> bool:
        return self._tracking_enabled

    def detect(
        self,
        image: ImageArray,
        *,
        frame_index: int | None = None,
    ) -> DetectionBatch:
        if image.ndim != 3 or image.shape[2] != 3:
            raise ValueError(f"image must be HxWx3 BGR uint8, got shape {image.shape}.")
        if image.dtype != np.uint8:
            raise ValueError(f"image dtype must be uint8, got {image.dtype}.")

        height, width = int(image.shape[0]), int(image.shape[1])
        source = self._resolve_detections(frame_index)
        out: list[Detection] = []
        for det in source:
            bbox = det.bbox
            if self._normalized:
                bbox = BoundingBox(
                    x1=bbox.x1 * width,
                    y1=bbox.y1 * height,
                    x2=bbox.x2 * width,
                    y2=bbox.y2 * height,
                )
            track_id = det.track_id if self._tracking_enabled else None
            out.append(
                Detection(
                    bbox=bbox,
                    confidence=det.confidence,
                    class_id=det.class_id,
                    class_name=det.class_name,
                    track_id=track_id,
                    frame_index=frame_index if frame_index is not None else det.frame_index,
                    metadata=dict(det.metadata),
                )
            )
        return DetectionBatch(
            detections=tuple(out),
            model_name=self._model_name,
            device=self._device,
            frame_index=frame_index,
            inference_ms=self._inference_ms,
        )

    def _resolve_detections(self, frame_index: int | None) -> Sequence[Detection]:
        if self._script is None:
            return self._detections
        if callable(self._script):
            return self._script(frame_index)
        script_map = self._script
        if frame_index is None:
            return self._detections
        if frame_index in script_map:
            return script_map[frame_index]
        # Prefer exact keys; otherwise use the highest key <= frame_index.
        prior = [k for k in script_map if k <= frame_index]
        if not prior:
            return self._detections
        return script_map[max(prior)]


def default_fake_detections() -> tuple[Detection, ...]:
    """Two deterministic vehicle boxes used by contract tests."""
    return (
        Detection(
            bbox=BoundingBox(x1=10.0, y1=20.0, x2=110.0, y2=120.0),
            confidence=0.91,
            class_id=2,
            class_name="car",
            track_id="1",
        ),
        Detection(
            bbox=BoundingBox(x1=200.0, y1=50.0, x2=300.0, y2=180.0),
            confidence=0.77,
            class_id=7,
            class_name="truck",
            track_id="2",
        ),
    )

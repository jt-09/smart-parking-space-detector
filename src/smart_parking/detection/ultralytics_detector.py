"""Ultralytics YOLO adapter returning domain Detection objects."""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np

from smart_parking.detection.base import ImageArray
from smart_parking.detection.models import BoundingBox, Detection, DetectionBatch
from smart_parking.domain.parking import Detection as DomainDetection

logger = logging.getLogger(__name__)

# COCO class names retained by default for parking lots.
DEFAULT_ALLOWED_CLASSES: tuple[str, ...] = ("car", "motorcycle", "bus", "truck")


class UltralyticsDetector:
    """Configurable Ultralytics YOLO wrapper behind the Detector protocol.

    Domain/pipeline code must depend only on ``Detector`` / ``DetectionBatch``.
    This adapter owns all Ultralytics imports and types.
    """

    def __init__(
        self,
        *,
        model_name: str = "yolo26n.pt",
        device: str = "cpu",
        confidence: float = 0.30,
        iou: float = 0.50,
        allowed_classes: Sequence[str] | None = None,
        tracking_enabled: bool = False,
        tracker: str | None = None,
    ) -> None:
        if not model_name.strip():
            raise ValueError("model_name must be a non-empty string.")
        if not device.strip():
            raise ValueError("device must be a non-empty string.")
        if not 0.0 <= confidence <= 1.0:
            raise ValueError(f"confidence must be in [0, 1], got {confidence}.")
        if not 0.0 <= iou <= 1.0:
            raise ValueError(f"iou must be in [0, 1], got {iou}.")

        self._model_name = model_name
        self._device = device
        self._confidence = confidence
        self._iou = iou
        self._allowed_classes = tuple(
            c.strip().lower()
            for c in (allowed_classes if allowed_classes is not None else DEFAULT_ALLOWED_CLASSES)
            if c.strip()
        )
        if not self._allowed_classes:
            raise ValueError("allowed_classes must contain at least one non-empty class name.")
        self._tracking_enabled = tracking_enabled
        self._tracker = tracker
        self._model: Any | None = None
        self._name_to_id: dict[str, int] = {}

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def device(self) -> str:
        return self._device

    @property
    def tracking_enabled(self) -> bool:
        return self._tracking_enabled

    @property
    def confidence(self) -> float:
        return self._confidence

    @property
    def iou(self) -> float:
        return self._iou

    @property
    def allowed_classes(self) -> tuple[str, ...]:
        return self._allowed_classes

    def load(self) -> None:
        """Eagerly load the YOLO model (optional; ``detect`` loads lazily)."""
        self._ensure_model()

    def _ensure_model(self) -> Any:
        if self._model is not None:
            return self._model

        from ultralytics import YOLO  # type: ignore[attr-defined]

        logger.info(
            "Loading Ultralytics YOLO model=%s device=%s confidence=%.2f iou=%.2f "
            "allowed_classes=%s tracking=%s",
            self._model_name,
            self._device,
            self._confidence,
            self._iou,
            ",".join(self._allowed_classes),
            self._tracking_enabled,
        )
        model = YOLO(self._model_name)
        names = getattr(model, "names", None) or {}
        if isinstance(names, dict):
            self._name_to_id = {str(v).lower(): int(k) for k, v in names.items()}
        else:
            self._name_to_id = {str(n).lower(): i for i, n in enumerate(names)}
        self._model = model
        return model

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

        model = self._ensure_model()
        started = time.perf_counter()
        # Tracking is enabled in a follow-up commit; predict path is the default.
        results = model.predict(
            source=image,
            conf=self._confidence,
            iou=self._iou,
            device=self._device,
            classes=self._class_ids_filter(),
            verbose=False,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        detections = self._parse_results(results, frame_index=frame_index)
        return DetectionBatch(
            detections=detections,
            model_name=self._model_name,
            device=self._device,
            frame_index=frame_index,
            inference_ms=elapsed_ms,
        )

    def _class_ids_filter(self) -> list[int] | None:
        """Map allowed class names to model class ids; None means no filter."""
        if not self._name_to_id:
            return None
        ids = [self._name_to_id[name] for name in self._allowed_classes if name in self._name_to_id]
        return ids or None

    def _parse_results(
        self,
        results: Sequence[Any],
        *,
        frame_index: int | None,
    ) -> tuple[DomainDetection, ...]:
        allowed = set(self._allowed_classes)
        parsed: list[DomainDetection] = []
        for result in results:
            boxes = getattr(result, "boxes", None)
            if boxes is None:
                continue
            names = getattr(result, "names", None) or {}
            for box in boxes:
                cls_id = int(box.cls.item()) if hasattr(box.cls, "item") else int(box.cls)
                if isinstance(names, dict):
                    class_name = str(names.get(cls_id, cls_id)).lower()
                else:
                    class_name = str(names[cls_id]).lower() if cls_id < len(names) else str(cls_id)
                if class_name not in allowed:
                    continue
                conf = float(box.conf.item()) if hasattr(box.conf, "item") else float(box.conf)
                xyxy = box.xyxy[0]
                if hasattr(xyxy, "tolist"):
                    x1, y1, x2, y2 = (float(v) for v in xyxy.tolist())
                else:
                    x1, y1, x2, y2 = (float(v) for v in xyxy)
                track_id: str | None = None
                box_id = getattr(box, "id", None)
                if box_id is not None:
                    raw = box_id.item() if hasattr(box_id, "item") else box_id
                    track_id = str(int(raw))
                parsed.append(
                    Detection(
                        bbox=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2),
                        confidence=conf,
                        class_id=cls_id,
                        class_name=class_name,
                        track_id=track_id,
                        frame_index=frame_index,
                    )
                )
        return tuple(parsed)


def weights_available(model_name: str = "yolo26n.pt") -> bool:
    """Return True when a local weight file exists (no network check)."""
    path = Path(model_name)
    return path.is_file()

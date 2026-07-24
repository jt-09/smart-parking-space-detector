"""Detector protocol contracts, FakeDetector, and optional Ultralytics smoke."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

from smart_parking.detection import (
    DEFAULT_ALLOWED_CLASSES,
    DetectionBatch,
    Detector,
    UltralyticsDetector,
    weights_available,
)
from smart_parking.detection.fake import FakeDetector, default_fake_detections
from smart_parking.detection.models import BoundingBox, Detection
from smart_parking.detection.ultralytics_detector import UltralyticsDetector as Adapter


def _blank_frame(width: int = 320, height: int = 240) -> np.ndarray:
    return np.zeros((height, width, 3), dtype=np.uint8)


def test_fake_detector_satisfies_protocol() -> None:
    detector: Detector = FakeDetector(default_fake_detections())
    assert isinstance(detector, Detector)
    assert detector.model_name == "fake"
    assert detector.device == "cpu"
    assert detector.tracking_enabled is True


def test_fake_detector_returns_deterministic_boxes() -> None:
    detector = FakeDetector(default_fake_detections())
    batch = detector.detect(_blank_frame(), frame_index=3)
    assert isinstance(batch, DetectionBatch)
    assert batch.model_name == "fake"
    assert batch.device == "cpu"
    assert batch.frame_index == 3
    assert len(batch.detections) == 2
    first, second = batch.detections
    assert first.class_name == "car"
    assert first.bbox.as_xyxy() == (10.0, 20.0, 110.0, 120.0)
    assert first.confidence == pytest.approx(0.91)
    assert first.track_id == "1"
    assert first.frame_index == 3
    assert second.class_name == "truck"
    assert second.track_id == "2"


def test_fake_detector_normalized_boxes_scale_to_frame() -> None:
    dets = (
        Detection(
            bbox=BoundingBox(x1=0.1, y1=0.2, x2=0.5, y2=0.6),
            confidence=0.5,
            class_id=2,
            class_name="car",
            track_id="9",
        ),
    )
    detector = FakeDetector(dets, normalized=True)
    batch = detector.detect(_blank_frame(200, 100), frame_index=0)
    box = batch.detections[0].bbox
    assert box.x1 == pytest.approx(20.0)
    assert box.y1 == pytest.approx(20.0)
    assert box.x2 == pytest.approx(100.0)
    assert box.y2 == pytest.approx(60.0)


def test_fake_detector_can_suppress_track_ids() -> None:
    detector = FakeDetector(default_fake_detections(), tracking_enabled=False)
    batch = detector.detect(_blank_frame())
    assert all(d.track_id is None for d in batch.detections)


def test_fake_detector_rejects_bad_image_shape() -> None:
    detector = FakeDetector()
    with pytest.raises(ValueError, match="HxWx3"):
        detector.detect(np.zeros((10, 10), dtype=np.uint8))


def test_detection_batch_validation() -> None:
    with pytest.raises(ValueError, match="model_name"):
        DetectionBatch(detections=(), model_name=" ", device="cpu")
    with pytest.raises(ValueError, match="device"):
        DetectionBatch(detections=(), model_name="m", device="")
    with pytest.raises(ValueError, match="inference_ms"):
        DetectionBatch(detections=(), model_name="m", device="cpu", inference_ms=-1.0)


def test_default_allowed_classes_are_vehicles() -> None:
    assert DEFAULT_ALLOWED_CLASSES == ("car", "motorcycle", "bus", "truck")


def test_ultralytics_adapter_config_and_class_filter_setup() -> None:
    adapter = UltralyticsDetector(
        model_name="yolo26n.pt",
        device="cpu",
        confidence=0.4,
        iou=0.45,
        allowed_classes=["car", "bus", "person"],
        tracking_enabled=True,
    )
    assert adapter.model_name == "yolo26n.pt"
    assert adapter.device == "cpu"
    assert adapter.confidence == pytest.approx(0.4)
    assert adapter.iou == pytest.approx(0.45)
    assert adapter.allowed_classes == ("car", "bus", "person")
    assert adapter.tracking_enabled is True
    assert isinstance(adapter, Detector)


def test_ultralytics_adapter_rejects_invalid_thresholds() -> None:
    with pytest.raises(ValueError, match="confidence"):
        UltralyticsDetector(confidence=1.5)
    with pytest.raises(ValueError, match="iou"):
        UltralyticsDetector(iou=-0.1)
    with pytest.raises(ValueError, match="allowed_classes"):
        UltralyticsDetector(allowed_classes=["  "])


def test_ultralytics_parse_filters_classes_and_maps_track_ids() -> None:
    """Class filtering and track_id mapping must not require real weights."""

    class _Val:
        def __init__(self, value: float | int | tuple[float, ...]) -> None:
            self._value = value

        def item(self) -> float | int:
            assert not isinstance(self._value, tuple)
            return self._value

        def tolist(self) -> list[float]:
            if isinstance(self._value, tuple):
                return [float(v) for v in self._value]
            return [float(self._value)]

    class _Box:
        def __init__(
            self,
            *,
            cls_id: int,
            conf: float,
            xyxy: tuple[float, float, float, float],
            track_id: int | None,
        ) -> None:
            self.cls = _Val(cls_id)
            self.conf = _Val(conf)
            self.xyxy = [_Val(xyxy)]
            self.id = None if track_id is None else _Val(track_id)

    class _Result:
        names = {0: "person", 2: "car", 5: "bus", 7: "truck"}

        def __init__(self, boxes: list[_Box]) -> None:
            self.boxes = boxes

    adapter = UltralyticsDetector(
        allowed_classes=["car", "truck"],
        tracking_enabled=True,
    )
    adapter._name_to_id = {"person": 0, "car": 2, "bus": 5, "truck": 7}  # noqa: SLF001
    result = _Result(
        [
            _Box(cls_id=0, conf=0.99, xyxy=(1.0, 1.0, 2.0, 2.0), track_id=3),
            _Box(cls_id=2, conf=0.88, xyxy=(10.0, 20.0, 30.0, 40.0), track_id=7),
            _Box(cls_id=7, conf=0.70, xyxy=(50.0, 60.0, 70.0, 80.0), track_id=None),
        ]
    )
    parsed = adapter._parse_results([result], frame_index=5)  # noqa: SLF001
    assert len(parsed) == 2
    assert parsed[0].class_name == "car"
    assert parsed[0].track_id == "7"
    assert parsed[0].frame_index == 5
    assert parsed[0].bbox.as_xyxy() == (10.0, 20.0, 30.0, 40.0)
    assert parsed[1].class_name == "truck"
    assert parsed[1].track_id is None


def test_gitignore_still_ignores_pt_weights() -> None:
    root = Path(__file__).resolve().parents[2]
    gitignore = (root / ".gitignore").read_text(encoding="utf-8")
    assert "*.pt" in gitignore


def test_track_id_passthrough_on_parsed_detection() -> None:
    """Domain Detection carries track_id for occupancy attribution."""
    det = Detection(
        bbox=BoundingBox(x1=0, y1=0, x2=10, y2=10),
        confidence=0.8,
        class_id=2,
        class_name="car",
        track_id="42",
    )
    assert det.track_id == "42"


def _ultralytics_smoke_enabled() -> bool:
    if os.environ.get("ULTRALYTICS_SMOKE") != "1":
        return False
    return weights_available("yolo26n.pt") or weights_available("yolov8n.pt")


@pytest.mark.skipif(
    not _ultralytics_smoke_enabled(),
    reason="Set ULTRALYTICS_SMOKE=1 and provide local YOLO weights for smoke test",
)
def test_ultralytics_adapter_cpu_smoke() -> None:
    model = "yolo26n.pt" if weights_available("yolo26n.pt") else "yolov8n.pt"
    adapter = Adapter(
        model_name=model,
        device="cpu",
        confidence=0.25,
        tracking_enabled=False,
    )
    batch = adapter.detect(_blank_frame(640, 480), frame_index=0)
    assert batch.model_name == model
    assert batch.device == "cpu"
    assert isinstance(batch.detections, tuple)
    # Blank frame typically yields zero detections; contract is typed output.
    for det in batch.detections:
        assert det.class_name in adapter.allowed_classes
        assert 0.0 <= det.confidence <= 1.0

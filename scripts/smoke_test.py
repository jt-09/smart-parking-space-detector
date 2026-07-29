#!/usr/bin/env python3
"""Weight-free smoke checks for local and CI validation.

Validates:
1. package import and version
2. example YAML/JSON config loading
3. short synthetic pipeline run with FakeDetector
4. FastAPI TestClient health/status contracts
"""

from __future__ import annotations

import sys
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))


def _step(label: str) -> None:
    print(f"[smoke] {label}")


def check_import() -> None:
    _step("import smart_parking")
    import smart_parking

    assert smart_parking.__version__, "package version must be non-empty"
    print(f"  version={smart_parking.__version__}")


def check_config_examples() -> None:
    _step("load example config and parking map")
    from smart_parking.config.loader import load_parking_map, load_settings

    settings = load_settings(ROOT / "configs" / "app.example.yaml")
    parking = load_parking_map(ROOT / "configs" / "parking_spaces.example.json")
    assert settings.api.port > 0
    assert parking.spaces, "example parking map must define spaces"
    print(f"  spaces={len(parking.spaces)} camera={parking.camera_id}")


def check_synthetic_pipeline() -> None:
    _step("synthetic short pipeline (FakeDetector)")
    from smart_parking.config.models import (
        AppSettings,
        CameraSettings,
        GeometrySettings,
        Settings,
        StateSettings,
        VideoSettings,
    )
    from smart_parking.detection.fake import FakeDetector, default_fake_detections
    from smart_parking.domain.parking import ParkingMap, ParkingSpace, Point
    from smart_parking.pipeline.processor import ParkingProcessor
    from smart_parking.sources.synthetic import SyntheticFrameSource

    width, height, frames = 64, 48, 6
    mid = width // 2
    parking = ParkingMap(
        camera_id="smoke-cam",
        reference_width=width,
        reference_height=height,
        spaces=(
            ParkingSpace(
                id="A1",
                label="A1",
                polygon=(
                    Point(2, 8),
                    Point(mid - 2, 8),
                    Point(mid - 2, height - 4),
                    Point(2, height - 4),
                ),
            ),
            ParkingSpace(
                id="A2",
                label="A2",
                polygon=(
                    Point(mid + 2, 8),
                    Point(width - 2, 8),
                    Point(width - 2, height - 4),
                    Point(mid + 2, height - 4),
                ),
            ),
        ),
    )
    settings = Settings(
        app=AppSettings(output_dir="output"),
        camera=CameraSettings(id="smoke-cam", source="synthetic"),
        video=VideoSettings(
            process_every_n_frames=1,
            display=False,
            save_annotated_video=False,
        ),
        geometry=GeometrySettings(
            parking_map=Path("configs/parking_spaces.example.json"),
            candidate_score_threshold=0.05,
            occupied_enter_threshold=0.10,
            occupied_exit_threshold=0.05,
        ),
        state=StateSettings(
            mode="frames",
            enter_confirm_frames=1,
            exit_confirm_frames=1,
            unknown_after_invalid_frames=20,
        ),
    )
    source = SyntheticFrameSource(
        source_id="smoke",
        width=width,
        height=height,
        frame_count=frames,
        moving_rectangle=True,
        start_time=datetime(2026, 7, 29, 12, 0, 0, tzinfo=UTC),
    )
    detector = FakeDetector(default_fake_detections(), device="cpu")
    with tempfile.TemporaryDirectory() as tmp:
        run_settings = settings.model_copy(
            update={"app": AppSettings(output_dir=tmp)},
        )
        processor = ParkingProcessor(
            run_settings,
            parking,
            source,
            detector,
            run_id=str(uuid.uuid4()),
        )
        result = processor.run()
    assert result.metrics.frames_read >= frames
    assert result.metrics.frames_processed >= 1
    print(f"  frames_read={result.metrics.frames_read} processed={result.metrics.frames_processed}")


def check_api_client() -> None:
    _step("FastAPI TestClient health/status")
    from fastapi.testclient import TestClient

    from smart_parking.api.app import create_app
    from smart_parking.api.runtime import StatusStore, source_status_from_settings
    from smart_parking.config.models import Settings
    from smart_parking.domain.state import OccupancySnapshot, OccupancyState, SpaceOccupancy

    settings = Settings()
    now = datetime(2026, 7, 29, 12, 0, 0, tzinfo=UTC)
    snapshot = OccupancySnapshot(
        camera_id="smoke-cam",
        captured_at=now,
        run_id=str(uuid.uuid4()),
        spaces=(
            SpaceOccupancy("A1", OccupancyState.AVAILABLE, confidence=0.9),
            SpaceOccupancy("A2", OccupancyState.OCCUPIED, confidence=0.8),
        ),
    )
    store = StatusStore(source=source_status_from_settings(settings))
    app = create_app(settings=settings, store=store, snapshot=snapshot)
    client = TestClient(app)
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    status = client.get("/api/v1/status")
    assert status.status_code == 200
    body = status.json()
    assert body["total_spaces"] == 2
    assert body["available"] == 1
    assert body["occupied"] == 1
    print("  /health and /api/v1/status OK")


def main() -> int:
    check_import()
    check_config_examples()
    check_synthetic_pipeline()
    check_api_client()
    print("[smoke] all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

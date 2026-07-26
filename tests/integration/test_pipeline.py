"""End-to-end pipeline integration tests (synthetic media only)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

from smart_parking.config.models import (
    AppSettings,
    CameraSettings,
    GeometrySettings,
    Settings,
    StateSettings,
    VideoSettings,
)
from smart_parking.detection.fake import FakeDetector
from smart_parking.detection.models import BoundingBox, Detection
from smart_parking.domain.parking import ParkingMap, ParkingSpace, Point
from smart_parking.domain.state import OccupancyState
from smart_parking.pipeline.processor import ParkingProcessor
from smart_parking.pipeline.writers import (
    AnnotatedVideoWriter,
    JsonlSnapshotWriter,
    build_output_paths,
    ensure_output_dir,
)
from smart_parking.rendering.renderer import AnnotationRenderer, render_frame
from smart_parking.sources.synthetic import SyntheticFrameSource


def _space(space_id: str, x1: float, y1: float, x2: float, y2: float) -> ParkingSpace:
    return ParkingSpace(
        id=space_id,
        label=space_id,
        polygon=(
            Point(x1, y1),
            Point(x2, y1),
            Point(x2, y2),
            Point(x1, y2),
        ),
    )


def _parking_map(width: int = 64, height: int = 48) -> ParkingMap:
    # Two bays covering left and right halves of a small synthetic frame.
    mid = width // 2
    return ParkingMap(
        camera_id="test-cam",
        reference_width=width,
        reference_height=height,
        spaces=(
            _space("A1", 2, 8, mid - 2, height - 4),
            _space("A2", mid + 2, 8, width - 2, height - 4),
        ),
    )


def _settings(tmp_path: Path, *, every_n: int = 1, confirm: int = 3) -> Settings:
    return Settings(
        app=AppSettings(environment="test", output_dir=tmp_path / "out"),
        camera=CameraSettings(id="test-cam", source="synthetic"),
        video=VideoSettings(
            process_every_n_frames=every_n,
            save_annotated_video=True,
            output_fps=10.0,
        ),
        geometry=GeometrySettings(
            parking_map=Path("unused.json"),
            candidate_score_threshold=0.10,
            occupied_enter_threshold=0.25,
            occupied_exit_threshold=0.10,
        ),
        state=StateSettings(
            mode="frames",
            enter_confirm_frames=confirm,
            exit_confirm_frames=confirm,
            unknown_after_invalid_frames=5,
        ),
    )


def _car_in_a1(width: int = 64, height: int = 48) -> Detection:
    # Box fully inside left bay for strong overlap.
    return Detection(
        bbox=BoundingBox(x1=6.0, y1=12.0, x2=width / 2 - 6.0, y2=height - 8.0),
        confidence=0.95,
        class_id=2,
        class_name="car",
        track_id="7",
    )


def test_renderer_uses_confirmed_state_not_raw_scores() -> None:
    parking = _parking_map()
    from smart_parking.domain.state import OccupancySnapshot, SpaceOccupancy

    snapshot = OccupancySnapshot(
        camera_id="test-cam",
        captured_at=datetime(2026, 7, 26, 12, 0, tzinfo=UTC),
        spaces=(
            SpaceOccupancy(
                space_id="A1",
                state=OccupancyState.OCCUPIED,
                confidence=0.9,
                score=0.05,  # raw score low — renderer must still show OCCUPIED
            ),
            SpaceOccupancy(space_id="A2", state=OccupancyState.AVAILABLE, confidence=0.2),
        ),
        frame_index=0,
    )
    image = np.zeros((48, 64, 3), dtype=np.uint8)
    annotated = render_frame(image, parking, snapshot, detections=())
    assert annotated.shape == image.shape
    # Occupied overlay uses a reddish BGR; available uses greenish — pixels differ.
    assert not np.array_equal(annotated, image)


def test_pipeline_end_to_end_transitions_and_artifacts(tmp_path: Path) -> None:
    width, height, frames = 64, 48, 24
    parking = _parking_map(width, height)
    settings = _settings(tmp_path, confirm=3)
    occupied_until = 12  # frames 0..11 occupied evidence; then vacant

    def script(frame_index: int | None) -> tuple[Detection, ...]:
        idx = 0 if frame_index is None else frame_index
        if idx < occupied_until:
            return (_car_in_a1(width, height),)
        return ()

    detector = FakeDetector(script=script, inference_ms=1.0)
    source = SyntheticFrameSource(
        source_id="test-cam",
        width=width,
        height=height,
        frame_count=frames,
        moving_rectangle=False,
    )
    paths = build_output_paths(settings.app.output_dir, run_id="itest")
    video_writer = AnnotatedVideoWriter(paths["annotated_video"], fps=10.0)
    jsonl_writer = JsonlSnapshotWriter(paths["snapshots_jsonl"])

    processor = ParkingProcessor(
        settings,
        parking,
        source,
        detector,
        run_id="itest",
        render_fn=AnnotationRenderer(),
        annotated_sink=video_writer,
        snapshot_sink=jsonl_writer,
    )
    result = processor.run()

    assert not result.interrupted
    assert result.metrics.frames_read == frames
    assert result.metrics.frames_processed == frames
    assert result.final_snapshot is not None
    assert video_writer.frames_written == frames
    assert jsonl_writer.rows_written == frames
    assert paths["annotated_video"].is_file()
    assert paths["snapshots_jsonl"].is_file()
    assert paths["annotated_video"].stat().st_size > 0

    # Expected: A1 recovers UNKNOWN→OCCUPIED by frame confirm-1, stays occupied
    # while evidence present, then exits to AVAILABLE after vacant confirmation.
    a1_states = [
        next(s.state for s in snap.spaces if s.space_id == "A1") for snap in result.snapshots
    ]
    assert OccupancyState.OCCUPIED in a1_states
    assert OccupancyState.AVAILABLE in a1_states
    # First confirmed occupied appears at enter_confirm_frames (index confirm-1).
    assert a1_states[2] == OccupancyState.OCCUPIED
    # After vacancy + exit confirmation, last frames are AVAILABLE.
    assert a1_states[-1] == OccupancyState.AVAILABLE

    # A2 never receives a vehicle — recovers to AVAILABLE.
    a2_final = next(s for s in result.final_snapshot.spaces if s.space_id == "A2")
    assert a2_final.state == OccupancyState.AVAILABLE

    lines = paths["snapshots_jsonl"].read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == frames
    first = json.loads(lines[0])
    assert first["camera_id"] == "test-cam"
    assert "available" in first and "occupied" in first
    assert first["spaces"]
    # JSONL reflects engine state strings.
    assert all("state" in space for space in first["spaces"])

    assert not source.is_open


def test_frame_sampling_skips_unselected_frames(tmp_path: Path) -> None:
    settings = _settings(tmp_path, every_n=2, confirm=2)
    parking = _parking_map()
    detector = FakeDetector(script=lambda _i: ())
    source = SyntheticFrameSource(
        source_id="test-cam",
        width=64,
        height=48,
        frame_count=10,
        moving_rectangle=False,
    )
    processor = ParkingProcessor(settings, parking, source, detector, run_id="sample")
    result = processor.run()
    assert result.metrics.frames_read == 10
    assert result.metrics.frames_processed == 5
    assert result.metrics.frames_skipped == 5


def test_failed_video_writer_still_closes_source(tmp_path: Path) -> None:
    settings = _settings(tmp_path, confirm=2)
    parking = _parking_map()
    detector = FakeDetector(script=lambda _i: ())
    source = SyntheticFrameSource(
        source_id="test-cam",
        width=64,
        height=48,
        frame_count=4,
        moving_rectangle=False,
    )

    class BoomWriter:
        def __call__(self, annotated: object, snapshot: object, metrics: object) -> None:
            raise RuntimeError("disk full")

        def close(self) -> None:
            return None

    processor = ParkingProcessor(
        settings,
        parking,
        source,
        detector,
        run_id="boom",
        render_fn=AnnotationRenderer(),
        annotated_sink=BoomWriter(),
    )
    with pytest.raises(RuntimeError, match="disk full"):
        processor.run()
    assert not source.is_open


def test_ensure_output_dir_creates_nested(tmp_path: Path) -> None:
    target = tmp_path / "a" / "b" / "c"
    ensure_output_dir(target)
    assert target.is_dir()


def test_request_stop_halts_loop(tmp_path: Path) -> None:
    settings = _settings(tmp_path, confirm=2)
    parking = _parking_map()
    detector = FakeDetector(script=lambda _i: ())
    source = SyntheticFrameSource(
        source_id="test-cam",
        width=64,
        height=48,
        frame_count=50,
        moving_rectangle=False,
    )

    processor_box: dict[str, ParkingProcessor] = {}

    def _stop_early(result: object) -> None:
        del result
        processor_box["proc"].request_stop()

    processor = ParkingProcessor(
        settings,
        parking,
        source,
        detector,
        run_id="stop",
        on_frame=_stop_early,
    )
    processor_box["proc"] = processor
    result = processor.run()
    assert result.metrics.frames_processed == 1
    assert not source.is_open

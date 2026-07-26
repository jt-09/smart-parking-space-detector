"""Unit tests for pipeline snapshot helpers and output writers."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

from smart_parking.domain.state import OccupancySnapshot, OccupancyState, SpaceOccupancy
from smart_parking.pipeline.snapshot import PipelineMetrics, snapshot_to_dict
from smart_parking.pipeline.writers import (
    AnnotatedVideoWriter,
    JsonlSnapshotWriter,
    build_output_paths,
    write_metrics_json,
)


def _snapshot() -> OccupancySnapshot:
    return OccupancySnapshot(
        camera_id="cam",
        captured_at=datetime(2026, 7, 26, 10, 0, tzinfo=UTC),
        spaces=(SpaceOccupancy(space_id="A1", state=OccupancyState.OCCUPIED, confidence=0.8),),
        frame_index=3,
        run_id="r1",
    )


def test_snapshot_to_dict_includes_counts_and_metrics() -> None:
    metrics = PipelineMetrics(frames_processed=3, e2e_fps=12.5, last_inference_ms=8.0)
    payload = snapshot_to_dict(_snapshot(), metrics=metrics)
    assert payload["camera_id"] == "cam"
    assert payload["occupied"] == 1
    assert payload["timestamp"].endswith("Z")
    assert payload["metrics"]["e2e_fps"] == 12.5
    assert payload["spaces"][0]["state"] == "occupied"


def test_jsonl_and_metrics_writers(tmp_path: Path) -> None:
    paths = build_output_paths(tmp_path / "out", run_id="u1")
    metrics = PipelineMetrics(frames_processed=1, e2e_fps=5.0)
    with JsonlSnapshotWriter(paths["snapshots_jsonl"]) as writer:
        writer.write(_snapshot(), metrics)
    write_metrics_json(paths["metrics_json"], metrics, run_id="u1")
    lines = paths["snapshots_jsonl"].read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["frame_index"] == 3
    assert json.loads(paths["metrics_json"].read_text(encoding="utf-8"))["run_id"] == "u1"


def test_annotated_video_writer_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "clip.mp4"
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    frame[:] = (40, 80, 120)
    with AnnotatedVideoWriter(path, fps=5.0) as writer:
        writer.write(frame)
        writer.write(frame)
    assert path.is_file()
    assert path.stat().st_size > 0
    assert writer.frames_written == 2


def test_annotated_video_writer_rejects_bad_fps(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="fps"):
        AnnotatedVideoWriter(tmp_path / "x.mp4", fps=0)

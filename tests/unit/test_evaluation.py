"""Unit tests for occupancy evaluation metrics and ground-truth loading."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from smart_parking.domain.state import (
    OccupancySnapshot,
    OccupancyState,
    SpaceOccupancy,
)
from smart_parking.evaluation.ground_truth import (
    GroundTruthLabel,
    load_ground_truth,
    load_ground_truth_csv,
    load_ground_truth_json,
)
from smart_parking.evaluation.metrics import (
    PredictedLabel,
    evaluate_occupancy,
    normalize_eval_state,
    percentile,
    predictions_from_snapshots,
)
from smart_parking.evaluation.predictions import load_predictions
from smart_parking.evaluation.report import format_benchmark_report
from smart_parking.evaluation.throughput import (
    collect_hardware_info,
    run_throughput_benchmark,
)


def test_percentile_nearest_rank() -> None:
    values = [10.0, 20.0, 30.0, 40.0, 50.0]
    assert percentile(values, 0) == 10.0
    assert percentile(values, 100) == 50.0
    assert percentile(values, 50) == 30.0
    assert percentile(values, 95) == 50.0


def test_normalize_eval_state_collapses_pending() -> None:
    assert normalize_eval_state(OccupancyState.PENDING_OCCUPIED) == OccupancyState.OCCUPIED
    assert normalize_eval_state(OccupancyState.PENDING_AVAILABLE) == OccupancyState.AVAILABLE
    assert normalize_eval_state(OccupancyState.UNKNOWN) == OccupancyState.UNKNOWN


def test_perfect_accuracy_on_toy_labels() -> None:
    ground = (
        GroundTruthLabel(0.0, "A1", OccupancyState.AVAILABLE),
        GroundTruthLabel(1.0, "A1", OccupancyState.OCCUPIED),
        GroundTruthLabel(2.0, "A1", OccupancyState.AVAILABLE),
        GroundTruthLabel(0.0, "A2", OccupancyState.OCCUPIED),
        GroundTruthLabel(1.0, "A2", OccupancyState.OCCUPIED),
        GroundTruthLabel(2.0, "A2", OccupancyState.AVAILABLE),
    )
    preds = (
        PredictedLabel(0.0, "A1", OccupancyState.AVAILABLE),
        PredictedLabel(1.0, "A1", OccupancyState.OCCUPIED),
        PredictedLabel(2.0, "A1", OccupancyState.AVAILABLE),
        PredictedLabel(0.0, "A2", OccupancyState.OCCUPIED),
        PredictedLabel(1.0, "A2", OccupancyState.OCCUPIED),
        PredictedLabel(2.0, "A2", OccupancyState.AVAILABLE),
    )
    report = evaluate_occupancy(ground, preds, match_tolerance=0.0)
    assert report.macro_accuracy == pytest.approx(1.0)
    assert report.per_space_accuracy["A1"] == pytest.approx(1.0)
    assert report.per_space_accuracy["A2"] == pytest.approx(1.0)
    assert report.occupied.precision == pytest.approx(1.0)
    assert report.occupied.recall == pytest.approx(1.0)
    assert report.occupied.f1 == pytest.approx(1.0)
    assert report.transitions.precision == pytest.approx(1.0)
    assert report.transitions.recall == pytest.approx(1.0)
    assert report.transitions.false_flips == 0
    assert report.transitions.mean_latency == pytest.approx(0.0)
    assert report.transitions.p95_latency == pytest.approx(0.0)


def test_occupied_precision_recall_f1_known_confusion() -> None:
    # 2 TP, 1 FP, 1 FN → P=2/3, R=2/3, F1=2/3
    ground = (
        GroundTruthLabel(0, "S", OccupancyState.OCCUPIED),
        GroundTruthLabel(1, "S", OccupancyState.OCCUPIED),
        GroundTruthLabel(2, "S", OccupancyState.AVAILABLE),
        GroundTruthLabel(3, "S", OccupancyState.OCCUPIED),
    )
    preds = (
        PredictedLabel(0, "S", OccupancyState.OCCUPIED),  # TP
        PredictedLabel(1, "S", OccupancyState.OCCUPIED),  # TP
        PredictedLabel(2, "S", OccupancyState.OCCUPIED),  # FP
        PredictedLabel(3, "S", OccupancyState.AVAILABLE),  # FN
    )
    report = evaluate_occupancy(ground, preds)
    assert report.occupied.true_positives == 2
    assert report.occupied.false_positives == 1
    assert report.occupied.false_negatives == 1
    assert report.occupied.precision == pytest.approx(2 / 3)
    assert report.occupied.recall == pytest.approx(2 / 3)
    assert report.occupied.f1 == pytest.approx(2 / 3)


def test_transition_latency_and_false_flips() -> None:
    ground = (
        GroundTruthLabel(0.0, "A1", OccupancyState.AVAILABLE),
        GroundTruthLabel(5.0, "A1", OccupancyState.OCCUPIED),
        GroundTruthLabel(20.0, "A1", OccupancyState.AVAILABLE),
    )
    # Late occupy (+2), exact vacate, plus a spurious flip at t=12.
    preds = (
        PredictedLabel(0.0, "A1", OccupancyState.AVAILABLE),
        PredictedLabel(7.0, "A1", OccupancyState.OCCUPIED),
        PredictedLabel(12.0, "A1", OccupancyState.AVAILABLE),
        PredictedLabel(13.0, "A1", OccupancyState.OCCUPIED),
        PredictedLabel(20.0, "A1", OccupancyState.AVAILABLE),
    )
    report = evaluate_occupancy(ground, preds, match_tolerance=None)
    assert report.transitions.true_positives == 2
    assert report.transitions.false_flips >= 1
    assert report.transitions.mean_latency is not None
    assert report.transitions.p95_latency is not None
    # Matched latencies include +2.0 for occupy and 0.0 for vacate.
    assert report.transitions.mean_latency == pytest.approx(1.0)


def test_per_space_and_macro_accuracy() -> None:
    ground = (
        GroundTruthLabel(0, "A", OccupancyState.AVAILABLE),
        GroundTruthLabel(1, "A", OccupancyState.OCCUPIED),
        GroundTruthLabel(0, "B", OccupancyState.OCCUPIED),
        GroundTruthLabel(1, "B", OccupancyState.OCCUPIED),
    )
    preds = (
        PredictedLabel(0, "A", OccupancyState.AVAILABLE),  # correct
        PredictedLabel(1, "A", OccupancyState.AVAILABLE),  # wrong
        PredictedLabel(0, "B", OccupancyState.OCCUPIED),  # correct
        PredictedLabel(1, "B", OccupancyState.OCCUPIED),  # correct
    )
    report = evaluate_occupancy(ground, preds)
    assert report.per_space_accuracy["A"] == pytest.approx(0.5)
    assert report.per_space_accuracy["B"] == pytest.approx(1.0)
    assert report.macro_accuracy == pytest.approx(0.75)


def test_load_ground_truth_csv_and_json(tmp_path: Path) -> None:
    csv_path = tmp_path / "gt.csv"
    csv_path.write_text(
        "frame_or_time,space_id,expected_state\n"
        "0.0,A-001,available\n"
        "3.2,A-001,occupied\n"
        "18.7,A-001,available\n",
        encoding="utf-8",
    )
    labels = load_ground_truth_csv(csv_path)
    assert len(labels) == 3
    assert labels[1].space_id == "A-001"
    assert labels[1].expected_state == OccupancyState.OCCUPIED

    json_path = tmp_path / "gt.json"
    json_path.write_text(
        '{"labels":[{"frame_or_time":1,"space_id":"B","expected_state":"occupied"}]}',
        encoding="utf-8",
    )
    assert load_ground_truth_json(json_path)[0].space_id == "B"
    assert load_ground_truth(csv_path)[0].frame_or_time == pytest.approx(0.0)

    jsonl_path = tmp_path / "gt.jsonl"
    jsonl_path.write_text(
        '{"frame_or_time":2,"space_id":"C","expected_state":"available"}\n',
        encoding="utf-8",
    )
    assert load_ground_truth(jsonl_path)[0].space_id == "C"


def test_ground_truth_validation_errors(tmp_path: Path) -> None:
    from smart_parking.evaluation.ground_truth import parse_expected_state

    with pytest.raises(ValueError, match="non-empty"):
        GroundTruthLabel(0.0, "  ", OccupancyState.AVAILABLE)
    with pytest.raises(ValueError, match="available, occupied, or unknown"):
        GroundTruthLabel(0.0, "A1", OccupancyState.PENDING_OCCUPIED)
    with pytest.raises(ValueError, match="Invalid expected_state"):
        parse_expected_state("busy")

    bad_csv = tmp_path / "bad.csv"
    bad_csv.write_text("frame_or_time,space_id\n0,A1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing required columns"):
        load_ground_truth_csv(bad_csv)

    empty_csv = tmp_path / "empty.csv"
    empty_csv.write_text(
        "frame_or_time,space_id,expected_state\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="No ground-truth"):
        load_ground_truth_csv(empty_csv)

    bad_json = tmp_path / "bad.json"
    bad_json.write_text('{"nope": []}', encoding="utf-8")
    with pytest.raises(ValueError, match="labels"):
        load_ground_truth_json(bad_json)

    with pytest.raises(ValueError, match="Unsupported"):
        load_ground_truth(tmp_path / "gt.txt")


def test_load_predictions_csv(tmp_path: Path) -> None:
    path = tmp_path / "pred.csv"
    path.write_text(
        "frame_or_time,space_id,predicted_state\n0,A1,available\n1,A1,occupied\n",
        encoding="utf-8",
    )
    preds = load_predictions(path)
    assert preds[1].predicted_state == OccupancyState.OCCUPIED

    json_path = tmp_path / "pred.json"
    json_path.write_text(
        '{"predictions":[{"frame_or_time":0,"space_id":"A1","predicted_state":"occupied"}]}',
        encoding="utf-8",
    )
    assert load_predictions(json_path)[0].space_id == "A1"

    alias = tmp_path / "alias.json"
    alias.write_text(
        '[{"frame_or_time":1,"space_id":"B","expected_state":"available"}]',
        encoding="utf-8",
    )
    assert load_predictions(alias)[0].predicted_state == OccupancyState.AVAILABLE


def test_load_predictions_errors(tmp_path: Path) -> None:
    empty = tmp_path / "empty.csv"
    empty.write_text("frame_or_time,space_id,predicted_state\n", encoding="utf-8")
    with pytest.raises(ValueError, match="No prediction"):
        load_predictions(empty)
    with pytest.raises(ValueError, match="Unsupported"):
        load_predictions(tmp_path / "x.txt")
    bad = tmp_path / "bad.json"
    bad.write_text('{"predictions":[]}', encoding="utf-8")
    with pytest.raises(ValueError, match="No prediction"):
        load_predictions(bad)


def test_predictions_from_snapshots() -> None:
    snap = OccupancySnapshot(
        camera_id="cam",
        captured_at=datetime(2026, 7, 27, 12, 0, tzinfo=UTC),
        frame_index=4,
        spaces=(SpaceOccupancy(space_id="A1", state=OccupancyState.OCCUPIED, confidence=0.9),),
    )
    preds = predictions_from_snapshots([snap])
    assert len(preds) == 1
    assert preds[0].frame_or_time == pytest.approx(4.0)
    assert preds[0].predicted_state == OccupancyState.OCCUPIED

    timed = predictions_from_snapshots([snap], use_frame_index=False)
    assert timed[0].frame_or_time == pytest.approx(snap.captured_at.timestamp())


def test_throughput_benchmark_runs_without_yolo(tmp_path: Path) -> None:
    result = run_throughput_benchmark(
        frame_count=8,
        width=64,
        height=48,
        output_dir=tmp_path / "bench",
        inference_ms=0.1,
    )
    assert result.frames_read == 8
    assert result.frames_processed == 8
    assert result.e2e_fps > 0
    assert result.decode_fps > 0
    assert result.detector == "fake"
    assert result.hardware.python_version
    assert result.as_dict()["peak_rss_mib"] is None or result.as_dict()["peak_rss_mib"] >= 0
    hw = collect_hardware_info()
    assert hw.system
    assert hw.as_dict()["python_version"]

    from smart_parking.evaluation.metrics import BinaryClassMetrics
    from smart_parking.evaluation.report import (
        format_occupancy_section,
        report_to_dict,
        write_benchmark_report,
    )

    occ = evaluate_occupancy(
        (GroundTruthLabel(0, "A1", OccupancyState.AVAILABLE),),
        (PredictedLabel(0, "A1", OccupancyState.AVAILABLE),),
    )
    text = format_benchmark_report(
        throughput=result,
        occupancy=occ,
        notes=["toy note"],
    )
    assert "Throughput" in text
    assert "Occupancy accuracy" in text
    assert "toy note" in text
    assert "macro_accuracy" in format_occupancy_section(occ)
    assert BinaryClassMetrics(1, 0, 0, 0).f1 == pytest.approx(1.0)
    payload = report_to_dict(throughput=result, occupancy=occ)
    assert "throughput" in payload and "occupancy" in payload
    dest = write_benchmark_report(tmp_path / "report.txt", text)
    assert dest.read_text(encoding="utf-8") == text


def test_throughput_rejects_invalid_args(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="frame_count"):
        run_throughput_benchmark(frame_count=0, output_dir=tmp_path)
    with pytest.raises(ValueError, match="too small"):
        run_throughput_benchmark(width=8, height=8, output_dir=tmp_path)


def test_match_tolerance_skips_distant_predictions() -> None:
    ground = (GroundTruthLabel(0.0, "A1", OccupancyState.OCCUPIED),)
    preds = (PredictedLabel(10.0, "A1", OccupancyState.OCCUPIED),)
    report = evaluate_occupancy(ground, preds, match_tolerance=0.0)
    assert report.matched_count == 0
    assert report.macro_accuracy == pytest.approx(0.0)


def test_evaluate_requires_labels() -> None:
    with pytest.raises(ValueError, match="ground_truth"):
        evaluate_occupancy([], [])


def test_unknown_samples_skipped_in_transitions() -> None:
    ground = (
        GroundTruthLabel(0, "A1", OccupancyState.AVAILABLE),
        GroundTruthLabel(1, "A1", OccupancyState.UNKNOWN),
        GroundTruthLabel(2, "A1", OccupancyState.OCCUPIED),
    )
    preds = (
        PredictedLabel(0, "A1", OccupancyState.AVAILABLE),
        PredictedLabel(1, "A1", OccupancyState.UNKNOWN),
        PredictedLabel(2, "A1", OccupancyState.OCCUPIED),
    )
    report = evaluate_occupancy(ground, preds)
    assert report.transitions.true_positives == 1
    assert report.as_dict()["transitions"]["false_flips"] == 0

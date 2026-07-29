"""Repeatable occupancy evaluation and performance benchmarks."""

from smart_parking.evaluation.ground_truth import (
    GroundTruthLabel,
    load_ground_truth,
    load_ground_truth_csv,
    load_ground_truth_json,
    parse_expected_state,
)
from smart_parking.evaluation.metrics import (
    BinaryClassMetrics,
    OccupancyEvaluationReport,
    PredictedLabel,
    TransitionMetrics,
    evaluate_occupancy,
    normalize_eval_state,
    percentile,
    predictions_from_snapshots,
)
from smart_parking.evaluation.predictions import (
    load_predictions,
    load_predictions_csv,
    load_predictions_json,
)

__all__ = [
    "BinaryClassMetrics",
    "GroundTruthLabel",
    "OccupancyEvaluationReport",
    "PredictedLabel",
    "TransitionMetrics",
    "evaluate_occupancy",
    "load_ground_truth",
    "load_ground_truth_csv",
    "load_ground_truth_json",
    "load_predictions",
    "load_predictions_csv",
    "load_predictions_json",
    "normalize_eval_state",
    "parse_expected_state",
    "percentile",
    "predictions_from_snapshots",
]

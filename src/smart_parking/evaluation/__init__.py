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
from smart_parking.evaluation.report import (
    format_benchmark_report,
    format_occupancy_section,
    format_throughput_section,
    write_benchmark_report,
)
from smart_parking.evaluation.throughput import (
    HardwareInfo,
    ThroughputResult,
    collect_hardware_info,
    current_rss_bytes,
    run_throughput_benchmark,
)

__all__ = [
    "BinaryClassMetrics",
    "GroundTruthLabel",
    "HardwareInfo",
    "OccupancyEvaluationReport",
    "PredictedLabel",
    "ThroughputResult",
    "TransitionMetrics",
    "collect_hardware_info",
    "current_rss_bytes",
    "evaluate_occupancy",
    "format_benchmark_report",
    "format_occupancy_section",
    "format_throughput_section",
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
    "run_throughput_benchmark",
    "write_benchmark_report",
]

"""Occupancy and transition metrics for ground-truth evaluation."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from smart_parking.domain.state import OccupancySnapshot, OccupancyState
from smart_parking.evaluation.ground_truth import GroundTruthLabel

_OCCUPIED_LIKE = {
    OccupancyState.OCCUPIED,
    OccupancyState.PENDING_OCCUPIED,
}
_AVAILABLE_LIKE = {
    OccupancyState.AVAILABLE,
    OccupancyState.PENDING_AVAILABLE,
}


@dataclass(frozen=True, slots=True)
class PredictedLabel:
    """One predicted occupancy label aligned to a frame index or timestamp."""

    frame_or_time: float
    space_id: str
    predicted_state: OccupancyState


@dataclass(frozen=True, slots=True)
class BinaryClassMetrics:
    """Binary classification counts and ratios for the occupied class."""

    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int

    @property
    def precision(self) -> float:
        denom = self.true_positives + self.false_positives
        return self.true_positives / denom if denom else 0.0

    @property
    def recall(self) -> float:
        denom = self.true_positives + self.false_negatives
        return self.true_positives / denom if denom else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return (2.0 * p * r / (p + r)) if (p + r) else 0.0

    def as_dict(self) -> dict[str, float | int]:
        return {
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "true_negatives": self.true_negatives,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
        }


@dataclass(frozen=True, slots=True)
class TransitionMetrics:
    """State-transition matching quality and latency statistics."""

    true_positives: int
    false_positives: int
    false_negatives: int
    false_flips: int
    latencies: tuple[float, ...] = ()

    @property
    def precision(self) -> float:
        denom = self.true_positives + self.false_positives
        return self.true_positives / denom if denom else 0.0

    @property
    def recall(self) -> float:
        denom = self.true_positives + self.false_negatives
        return self.true_positives / denom if denom else 0.0

    @property
    def mean_latency(self) -> float | None:
        if not self.latencies:
            return None
        return sum(self.latencies) / len(self.latencies)

    @property
    def p95_latency(self) -> float | None:
        if not self.latencies:
            return None
        return percentile(self.latencies, 95.0)

    def as_dict(self) -> dict[str, float | int | None]:
        return {
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "false_flips": self.false_flips,
            "precision": self.precision,
            "recall": self.recall,
            "mean_latency": self.mean_latency,
            "p95_latency": self.p95_latency,
        }


@dataclass(frozen=True, slots=True)
class OccupancyEvaluationReport:
    """Aggregated occupancy accuracy and transition metrics."""

    per_space_accuracy: dict[str, float]
    macro_accuracy: float
    occupied: BinaryClassMetrics
    transitions: TransitionMetrics
    sample_count: int
    matched_count: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "sample_count": self.sample_count,
            "matched_count": self.matched_count,
            "per_space_accuracy": dict(self.per_space_accuracy),
            "macro_accuracy": self.macro_accuracy,
            "occupied": self.occupied.as_dict(),
            "transitions": self.transitions.as_dict(),
        }


@dataclass(frozen=True, slots=True)
class _Transition:
    space_id: str
    from_state: str
    to_state: str
    at: float


def normalize_eval_state(state: OccupancyState) -> OccupancyState:
    """Collapse pending states toward their intended confirmed label."""
    if state in _OCCUPIED_LIKE:
        return OccupancyState.OCCUPIED
    if state in _AVAILABLE_LIKE:
        return OccupancyState.AVAILABLE
    return OccupancyState.UNKNOWN


def percentile(values: Iterable[float], pct: float) -> float:
    """Nearest-rank percentile for a non-empty sequence (pct in 0..100)."""
    ordered = sorted(float(v) for v in values)
    if not ordered:
        raise ValueError("percentile requires at least one value.")
    if pct <= 0:
        return ordered[0]
    if pct >= 100:
        return ordered[-1]
    rank = int(round((pct / 100.0) * (len(ordered) - 1)))
    return ordered[rank]


def predictions_from_snapshots(
    snapshots: Iterable[OccupancySnapshot],
    *,
    use_frame_index: bool = True,
) -> tuple[PredictedLabel, ...]:
    """Flatten occupancy snapshots into per-space predicted labels."""
    labels: list[PredictedLabel] = []
    for snap in snapshots:
        if use_frame_index and snap.frame_index is not None:
            key = float(snap.frame_index)
        else:
            # Seconds since epoch — useful when ground truth uses timestamps.
            key = snap.captured_at.timestamp()
        for space in snap.spaces:
            labels.append(
                PredictedLabel(
                    frame_or_time=key,
                    space_id=space.space_id,
                    predicted_state=space.state,
                )
            )
    return tuple(labels)


def _index_predictions(
    predictions: Iterable[PredictedLabel],
) -> dict[str, list[PredictedLabel]]:
    by_space: dict[str, list[PredictedLabel]] = defaultdict(list)
    for pred in predictions:
        by_space[pred.space_id].append(pred)
    for space_id in by_space:
        by_space[space_id].sort(key=lambda item: item.frame_or_time)
    return by_space


def _nearest_prediction(
    preds: list[PredictedLabel],
    target: float,
    *,
    tolerance: float | None,
) -> PredictedLabel | None:
    if not preds:
        return None
    best = min(preds, key=lambda item: abs(item.frame_or_time - target))
    if tolerance is not None and abs(best.frame_or_time - target) > tolerance:
        return None
    return best


def _extract_transitions(
    labels: Iterable[tuple[float, OccupancyState]],
    *,
    space_id: str,
) -> list[_Transition]:
    ordered = sorted(labels, key=lambda item: item[0])
    transitions: list[_Transition] = []
    prev_state: OccupancyState | None = None
    for at, state in ordered:
        norm = normalize_eval_state(state)
        if norm == OccupancyState.UNKNOWN:
            # Skip unknown samples; keep the last confirmed state.
            continue
        if prev_state is None:
            prev_state = norm
            continue
        if norm != prev_state:
            transitions.append(
                _Transition(
                    space_id=space_id,
                    from_state=prev_state.value,
                    to_state=norm.value,
                    at=at,
                )
            )
            prev_state = norm
    return transitions


def _match_transitions(
    ground: list[_Transition],
    predicted: list[_Transition],
    *,
    max_latency: float | None,
) -> TransitionMetrics:
    """Greedy match predicted transitions to ground-truth by space and type."""
    remaining = list(predicted)
    tp = 0
    latencies: list[float] = []
    for gt in ground:
        best_idx: int | None = None
        best_latency = float("inf")
        for idx, pred in enumerate(remaining):
            if pred.space_id != gt.space_id:
                continue
            if pred.from_state != gt.from_state or pred.to_state != gt.to_state:
                continue
            latency = pred.at - gt.at
            if max_latency is not None and abs(latency) > max_latency:
                continue
            if abs(latency) < abs(best_latency):
                best_latency = latency
                best_idx = idx
        if best_idx is None:
            continue
        tp += 1
        latencies.append(best_latency)
        remaining.pop(best_idx)

    fn = len(ground) - tp
    fp = len(remaining)
    # False flips: unmatched predicted transitions (spurious state changes).
    false_flips = fp
    return TransitionMetrics(
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        false_flips=false_flips,
        latencies=tuple(latencies),
    )


@dataclass
class _Accumulators:
    per_space_correct: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    per_space_total: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0
    matched: int = 0


def evaluate_occupancy(
    ground_truth: Iterable[GroundTruthLabel],
    predictions: Iterable[PredictedLabel],
    *,
    match_tolerance: float | None = 0.0,
    transition_max_latency: float | None = None,
) -> OccupancyEvaluationReport:
    """Compute accuracy, occupied-class, and transition metrics.

    Parameters
    ----------
    match_tolerance:
        Maximum absolute ``frame_or_time`` distance when pairing a ground-truth
        label to a prediction. ``0.0`` requires an exact key match; ``None``
        always takes the nearest prediction for that space.
    transition_max_latency:
        Optional absolute latency bound when matching transitions.
    """
    gt_list = list(ground_truth)
    if not gt_list:
        raise ValueError("ground_truth must contain at least one label.")
    pred_by_space = _index_predictions(predictions)
    acc = _Accumulators()

    gt_series: dict[str, list[tuple[float, OccupancyState]]] = defaultdict(list)
    pred_series: dict[str, list[tuple[float, OccupancyState]]] = defaultdict(list)

    for label in gt_list:
        gt_series[label.space_id].append((label.frame_or_time, label.expected_state))
        preds = pred_by_space.get(label.space_id, [])
        match = _nearest_prediction(
            preds,
            label.frame_or_time,
            tolerance=match_tolerance,
        )
        if match is None:
            continue
        acc.matched += 1
        expected = normalize_eval_state(label.expected_state)
        predicted = normalize_eval_state(match.predicted_state)
        space_id = label.space_id
        acc.per_space_total[space_id] += 1
        if expected == predicted:
            acc.per_space_correct[space_id] += 1

        exp_occ = expected == OccupancyState.OCCUPIED
        pred_occ = predicted == OccupancyState.OCCUPIED
        if exp_occ and pred_occ:
            acc.tp += 1
        elif not exp_occ and pred_occ:
            acc.fp += 1
        elif exp_occ and not pred_occ:
            acc.fn += 1
        else:
            acc.tn += 1

    for space_id, preds in pred_by_space.items():
        for pred in preds:
            pred_series[space_id].append((pred.frame_or_time, pred.predicted_state))

    gt_transitions: list[_Transition] = []
    pred_transitions: list[_Transition] = []
    for space_id, series in gt_series.items():
        gt_transitions.extend(_extract_transitions(series, space_id=space_id))
    for space_id, series in pred_series.items():
        pred_transitions.extend(_extract_transitions(series, space_id=space_id))

    transition_metrics = _match_transitions(
        gt_transitions,
        pred_transitions,
        max_latency=transition_max_latency,
    )

    per_space_accuracy: dict[str, float] = {}
    for space_id, total in acc.per_space_total.items():
        correct = acc.per_space_correct.get(space_id, 0)
        per_space_accuracy[space_id] = correct / total if total else 0.0

    if per_space_accuracy:
        macro = sum(per_space_accuracy.values()) / len(per_space_accuracy)
    else:
        macro = 0.0

    return OccupancyEvaluationReport(
        per_space_accuracy=per_space_accuracy,
        macro_accuracy=macro,
        occupied=BinaryClassMetrics(
            true_positives=acc.tp,
            false_positives=acc.fp,
            false_negatives=acc.fn,
            true_negatives=acc.tn,
        ),
        transitions=transition_metrics,
        sample_count=len(gt_list),
        matched_count=acc.matched,
    )

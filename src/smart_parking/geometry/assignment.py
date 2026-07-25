"""Weighted occupancy scoring and deterministic one-to-one assignment."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from smart_parking.config.models import GeometrySettings
from smart_parking.domain.parking import Detection, ParkingMap, ParkingSpace
from smart_parking.geometry.overlap import OverlapMetrics, compute_overlap
from smart_parking.spaces.serialize import scale_parking_map


@dataclass(frozen=True, slots=True)
class ScoredCandidate:
    """A detection–space pair that passed the candidate score threshold."""

    detection_index: int
    space_id: str
    score: float
    metrics: OverlapMetrics


@dataclass(frozen=True, slots=True)
class SpaceAssignment:
    """One-to-one assignment of a detection to a parking space for a frame."""

    detection_index: int
    space_id: str
    score: float
    metrics: OverlapMetrics
    detection: Detection
    space: ParkingSpace


def weighted_occupancy_score(
    metrics: OverlapMetrics,
    settings: GeometrySettings,
) -> float:
    """Combine overlap ratios and containment flags with configured weights.

    score = w_space * space_overlap
          + w_vehicle * vehicle_overlap
          + w_center * centre_inside
          + w_bottom * bottom_centre_inside
    """
    return (
        settings.weight_space_overlap * metrics.space_overlap
        + settings.weight_vehicle_overlap * metrics.vehicle_overlap
        + settings.weight_center_inside * float(metrics.centre_inside)
        + settings.weight_bottom_center_inside * float(metrics.bottom_centre_inside)
    )


def score_detection_space(
    detection: Detection,
    space: ParkingSpace,
    settings: GeometrySettings,
    *,
    detection_index: int = 0,
) -> ScoredCandidate:
    """Score one detection against one parking space."""
    metrics = compute_overlap(
        detection,
        space,
        footprint_height_ratio=settings.footprint_height_ratio,
    )
    score = weighted_occupancy_score(metrics, settings)
    return ScoredCandidate(
        detection_index=detection_index,
        space_id=space.id,
        score=score,
        metrics=metrics,
    )


def map_for_frame(
    parking_map: ParkingMap,
    *,
    frame_width: int | None,
    frame_height: int | None,
) -> ParkingMap:
    """Scale the parking map to the frame resolution when they differ.

    When frame dimensions are omitted, the map is returned unchanged (caller
    already aligned coordinates).
    """
    if frame_width is None or frame_height is None:
        return parking_map
    return scale_parking_map(
        parking_map,
        target_width=frame_width,
        target_height=frame_height,
    )


def build_candidates(
    detections: Sequence[Detection],
    parking_map: ParkingMap,
    settings: GeometrySettings,
    *,
    frame_width: int | None = None,
    frame_height: int | None = None,
) -> list[ScoredCandidate]:
    """Build candidate pairs above the configured score threshold.

    Disabled spaces are ignored. Coordinates are scaled when ``frame_width`` /
    ``frame_height`` differ from the map reference resolution.
    """
    aligned = map_for_frame(
        parking_map,
        frame_width=frame_width,
        frame_height=frame_height,
    )
    spaces = aligned.enabled_spaces
    candidates: list[ScoredCandidate] = []
    threshold = settings.candidate_score_threshold

    for detection_index, detection in enumerate(detections):
        for space in spaces:
            candidate = score_detection_space(
                detection,
                space,
                settings,
                detection_index=detection_index,
            )
            if candidate.score >= threshold:
                candidates.append(candidate)
    return candidates


def assign_greedy(candidates: Sequence[ScoredCandidate]) -> list[ScoredCandidate]:
    """Greedy one-to-one assignment sorted by descending score.

    Ties are broken deterministically by space ID (ascending), then detection
    index (ascending). Each detection and each space may be chosen at most once.
    """
    ordered = sorted(
        candidates,
        key=lambda c: (-c.score, c.space_id, c.detection_index),
    )
    used_detections: set[int] = set()
    used_spaces: set[str] = set()
    chosen: list[ScoredCandidate] = []

    for candidate in ordered:
        if candidate.detection_index in used_detections:
            continue
        if candidate.space_id in used_spaces:
            continue
        used_detections.add(candidate.detection_index)
        used_spaces.add(candidate.space_id)
        chosen.append(candidate)

    # Stable output order: by space id for downstream consumers.
    return sorted(chosen, key=lambda c: (c.space_id, c.detection_index))


def assign_detections(
    detections: Sequence[Detection],
    parking_map: ParkingMap,
    settings: GeometrySettings,
    *,
    frame_width: int | None = None,
    frame_height: int | None = None,
) -> list[SpaceAssignment]:
    """Assign detections to parking spaces for one frame.

    Returns zero or one assignment per space and per detection. Unassigned
    spaces are omitted (callers treat missing evidence as zero / unknown).
    """
    aligned = map_for_frame(
        parking_map,
        frame_width=frame_width,
        frame_height=frame_height,
    )
    space_by_id = {space.id: space for space in aligned.enabled_spaces}
    candidates = build_candidates(
        detections,
        aligned,
        settings,
        frame_width=None,
        frame_height=None,
    )
    selected = assign_greedy(candidates)
    return [
        SpaceAssignment(
            detection_index=c.detection_index,
            space_id=c.space_id,
            score=c.score,
            metrics=c.metrics,
            detection=detections[c.detection_index],
            space=space_by_id[c.space_id],
        )
        for c in selected
    ]

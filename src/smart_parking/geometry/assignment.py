"""Weighted occupancy scoring for vehicle–space pairs."""

from __future__ import annotations

from dataclasses import dataclass

from smart_parking.config.models import GeometrySettings
from smart_parking.domain.parking import Detection, ParkingSpace
from smart_parking.geometry.overlap import OverlapMetrics, compute_overlap


@dataclass(frozen=True, slots=True)
class ScoredCandidate:
    """A detection–space pair with a weighted occupancy score."""

    detection_index: int
    space_id: str
    score: float
    metrics: OverlapMetrics


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

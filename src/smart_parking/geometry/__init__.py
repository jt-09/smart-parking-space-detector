"""Geometry engine: overlap metrics and vehicle-to-space assignment."""

from smart_parking.geometry.assignment import (
    ScoredCandidate,
    SpaceAssignment,
    assign_detections,
    assign_greedy,
    build_candidates,
    map_for_frame,
    score_detection_space,
    weighted_occupancy_score,
)
from smart_parking.geometry.overlap import (
    OverlapMetrics,
    compute_overlap,
    compute_overlap_polygons,
    detection_footprint,
)
from smart_parking.geometry.validation import (
    GeometryError,
    bbox_to_polygon,
    parking_space_to_polygon,
    points_to_polygon,
)

__all__ = [
    "GeometryError",
    "OverlapMetrics",
    "ScoredCandidate",
    "SpaceAssignment",
    "assign_detections",
    "assign_greedy",
    "bbox_to_polygon",
    "build_candidates",
    "compute_overlap",
    "compute_overlap_polygons",
    "detection_footprint",
    "map_for_frame",
    "parking_space_to_polygon",
    "points_to_polygon",
    "score_detection_space",
    "weighted_occupancy_score",
]

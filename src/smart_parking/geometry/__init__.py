"""Geometry engine: overlap metrics and vehicle-to-space assignment."""

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
    "bbox_to_polygon",
    "compute_overlap",
    "compute_overlap_polygons",
    "detection_footprint",
    "parking_space_to_polygon",
    "points_to_polygon",
]

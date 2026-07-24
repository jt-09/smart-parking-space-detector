"""Shapely polygon conversion and validation helpers for occupancy geometry."""

from __future__ import annotations

from collections.abc import Sequence

from shapely.geometry import Polygon
from shapely.validation import explain_validity

from smart_parking.domain.parking import BoundingBox, ParkingSpace, Point


class GeometryError(ValueError):
    """Raised when parking or vehicle geometry cannot be used for occupancy."""


def points_to_polygon(points: Sequence[Point], *, context: str) -> Polygon:
    """Convert domain points to a validated Shapely polygon.

    Raises:
        GeometryError: when fewer than three points are provided, the polygon is
            empty/invalid, or the area is non-positive. Messages are actionable.
    """
    if len(points) < 3:
        msg = (
            f"{context} needs at least 3 polygon vertices, got {len(points)}. "
            "Add more vertices so the shape encloses positive area."
        )
        raise GeometryError(msg)

    coords = [(p.x, p.y) for p in points]
    polygon = Polygon(coords)
    return _require_usable_polygon(polygon, context=context)


def parking_space_to_polygon(space: ParkingSpace) -> Polygon:
    """Convert a parking space to a validated Shapely polygon."""
    return points_to_polygon(space.polygon, context=f"Parking space '{space.id}'")


def bbox_to_polygon(bbox: BoundingBox, *, footprint_height_ratio: float = 1.0) -> Polygon:
    """Convert a detection box to a footprint polygon.

    When ``footprint_height_ratio`` is less than 1.0, only the lower portion of
    the box is used (elevated-camera bias toward the vehicle ground contact).
    """
    if not 0.0 < footprint_height_ratio <= 1.0:
        msg = (
            f"footprint_height_ratio must be in (0, 1], got {footprint_height_ratio}. "
            "Use a positive ratio such as 0.60 for the lower 60% of the box."
        )
        raise GeometryError(msg)

    if bbox.area <= 0.0:
        msg = (
            f"Detection bounding box has non-positive area ({bbox.area}). "
            "Reject empty detections before geometry scoring."
        )
        raise GeometryError(msg)

    height = bbox.height
    top = bbox.y2 - (height * footprint_height_ratio)
    polygon = Polygon(
        [
            (bbox.x1, top),
            (bbox.x2, top),
            (bbox.x2, bbox.y2),
            (bbox.x1, bbox.y2),
        ]
    )
    return _require_usable_polygon(
        polygon,
        context=(
            f"Detection footprint ({bbox.x1}, {bbox.y1}, {bbox.x2}, {bbox.y2}) "
            f"with footprint_height_ratio={footprint_height_ratio}"
        ),
    )


def _require_usable_polygon(polygon: Polygon, *, context: str) -> Polygon:
    if polygon.is_empty:
        msg = f"{context} produced an empty polygon. Redraw or fix the coordinates."
        raise GeometryError(msg)

    if not polygon.is_valid:
        reason = explain_validity(polygon)
        msg = (
            f"{context} is not a valid polygon ({reason}). "
            "Redraw so edges do not cross and the ring is properly closed."
        )
        raise GeometryError(msg)

    area = float(polygon.area)
    if area <= 0.0:
        msg = (
            f"{context} has non-positive area ({area}). "
            "Points may be collinear or duplicated; redraw the polygon."
        )
        raise GeometryError(msg)

    return polygon

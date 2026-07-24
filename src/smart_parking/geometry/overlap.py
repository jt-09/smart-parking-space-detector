"""Vehicle–space overlap metrics for occupancy scoring."""

from __future__ import annotations

from dataclasses import dataclass

from shapely.geometry import Point as ShapelyPoint
from shapely.geometry import Polygon

from smart_parking.domain.parking import BoundingBox, Detection, ParkingSpace, Point
from smart_parking.geometry.validation import (
    GeometryError,
    bbox_to_polygon,
    parking_space_to_polygon,
)


@dataclass(frozen=True, slots=True)
class OverlapMetrics:
    """Exact overlap quantities between one vehicle footprint and one space."""

    intersection_area: float
    space_overlap: float
    vehicle_overlap: float
    centre_inside: bool
    bottom_centre_inside: bool
    space_area: float
    vehicle_area: float


def detection_footprint(
    bbox: BoundingBox,
    *,
    footprint_height_ratio: float = 1.0,
) -> Polygon:
    """Return the Shapely footprint polygon for a detection bounding box."""
    return bbox_to_polygon(bbox, footprint_height_ratio=footprint_height_ratio)


def compute_overlap_polygons(
    vehicle: Polygon,
    space: Polygon,
    *,
    centre: Point,
    bottom_centre: Point,
) -> OverlapMetrics:
    """Compute overlap ratios and containment flags for known polygons.

    ``space_overlap`` = intersection / space area.
    ``vehicle_overlap`` = intersection / vehicle area.
    Containment uses Shapely ``covers`` so boundary points count as inside.
    """
    space_area = float(space.area)
    vehicle_area = float(vehicle.area)
    if space_area <= 0.0:
        raise GeometryError(
            "Parking space polygon has non-positive area. Validate the parking map before scoring."
        )
    if vehicle_area <= 0.0:
        raise GeometryError(
            "Vehicle footprint has non-positive area. Reject empty detections before scoring."
        )

    intersection_area = float(vehicle.intersection(space).area)
    return OverlapMetrics(
        intersection_area=intersection_area,
        space_overlap=intersection_area / space_area,
        vehicle_overlap=intersection_area / vehicle_area,
        centre_inside=bool(space.covers(ShapelyPoint(centre.x, centre.y))),
        bottom_centre_inside=bool(space.covers(ShapelyPoint(bottom_centre.x, bottom_centre.y))),
        space_area=space_area,
        vehicle_area=vehicle_area,
    )


def compute_overlap(
    detection: Detection,
    space: ParkingSpace,
    *,
    footprint_height_ratio: float = 1.0,
) -> OverlapMetrics:
    """Compute overlap metrics between a detection and a parking space."""
    vehicle = detection_footprint(
        detection.bbox,
        footprint_height_ratio=footprint_height_ratio,
    )
    space_poly = parking_space_to_polygon(space)

    # Centre / bottom-centre are taken from the full bbox (not the truncated footprint),
    # matching the domain BoundingBox helpers used elsewhere in the pipeline.
    return compute_overlap_polygons(
        vehicle,
        space_poly,
        centre=detection.bbox.center,
        bottom_centre=detection.bbox.bottom_center,
    )

"""Parking polygon geometry validation helpers."""

from __future__ import annotations

from smart_parking.domain.parking import ParkingMap, ParkingSpace, Point


class PolygonValidationError(ValueError):
    """Raised when a parking polygon fails geometry checks."""


def _orientation(a: Point, b: Point, c: Point) -> float:
    """Return cross-product sign for turn direction (positive = CCW)."""
    return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)


def _on_segment(a: Point, b: Point, c: Point, *, eps: float = 1e-9) -> bool:
    """Return True if point c lies on segment ab (inclusive), within eps."""
    return (
        min(a.x, b.x) - eps <= c.x <= max(a.x, b.x) + eps
        and min(a.y, b.y) - eps <= c.y <= max(a.y, b.y) + eps
    )


def _is_same_point(a: Point, b: Point, *, eps: float = 1e-9) -> bool:
    return abs(a.x - b.x) <= eps and abs(a.y - b.y) <= eps


def _collinear_interior_hit(a1: Point, a2: Point, point: Point) -> bool:
    """True when point lies on segment a1-a2 but is not an endpoint."""
    eps = 1e-9
    return (
        abs(_orientation(a1, a2, point)) <= eps
        and _on_segment(a1, a2, point, eps=eps)
        and not _is_same_point(point, a1, eps=eps)
        and not _is_same_point(point, a2, eps=eps)
    )


def segments_properly_intersect(a1: Point, a2: Point, b1: Point, b2: Point) -> bool:
    """Return True if segments a1-a2 and b1-b2 properly intersect.

    Shared endpoints of adjacent polygon edges are not treated as intersections.
    Collinear overlapping interiors are treated as intersections.
    """
    o1 = _orientation(a1, a2, b1)
    o2 = _orientation(a1, a2, b2)
    o3 = _orientation(b1, b2, a1)
    o4 = _orientation(b1, b2, a2)

    eps = 1e-9

    # General case: orientations differ on both segments.
    if ((o1 > eps and o2 < -eps) or (o1 < -eps and o2 > eps)) and (
        (o3 > eps and o4 < -eps) or (o3 < -eps and o4 > eps)
    ):
        return True

    # Collinear special cases: overlapping interiors (not mere endpoint touches).
    return bool(
        _collinear_interior_hit(a1, a2, b1)
        or _collinear_interior_hit(a1, a2, b2)
        or _collinear_interior_hit(b1, b2, a1)
        or _collinear_interior_hit(b1, b2, a2)
    )


def is_self_intersecting(polygon: tuple[Point, ...] | list[Point]) -> bool:
    """Return True if the closed polygon has crossing non-adjacent edges."""
    pts = tuple(polygon)
    n = len(pts)
    if n < 4:
        # Triangles cannot self-intersect without degenerate (zero-area) edges.
        return False

    edges = [(pts[i], pts[(i + 1) % n]) for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            # Skip adjacent edges (including first/last pairing).
            if abs(i - j) <= 1 or (i == 0 and j == n - 1):
                continue
            a1, a2 = edges[i]
            b1, b2 = edges[j]
            if segments_properly_intersect(a1, a2, b1, b2):
                return True
    return False


def validate_space_geometry(
    space: ParkingSpace,
    *,
    reference_width: int,
    reference_height: int,
) -> None:
    """Validate self-intersection, area, and bounds for one parking space."""
    # Self-intersection first: bow-tie polygons often report zero shoelace area.
    if is_self_intersecting(space.polygon):
        msg = (
            f"Parking space '{space.id}' polygon is self-intersecting (self-crossing). "
            "Redraw the polygon so edges do not cross."
        )
        raise PolygonValidationError(msg)

    if space.area <= 0.0:
        msg = (
            f"Parking space '{space.id}' polygon has non-positive area "
            f"({space.area}). Points may be collinear or duplicated; redraw the polygon."
        )
        raise PolygonValidationError(msg)

    for index, point in enumerate(space.polygon):
        if not (0.0 <= point.x <= float(reference_width)):
            msg = (
                f"Parking space '{space.id}' point {index} x={point.x} is outside "
                f"reference width [0, {reference_width}]."
            )
            raise PolygonValidationError(msg)
        if not (0.0 <= point.y <= float(reference_height)):
            msg = (
                f"Parking space '{space.id}' point {index} y={point.y} is outside "
                f"reference height [0, {reference_height}]."
            )
            raise PolygonValidationError(msg)


def validate_parking_map(parking_map: ParkingMap) -> ParkingMap:
    """Validate every space in a parking map; return the map unchanged on success."""
    for space in parking_map.spaces:
        validate_space_geometry(
            space,
            reference_width=parking_map.reference_width,
            reference_height=parking_map.reference_height,
        )
    return parking_map

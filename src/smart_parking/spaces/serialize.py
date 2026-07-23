"""Parking map JSON serialization and coordinate scaling."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from smart_parking.domain.parking import ParkingMap, ParkingSpace, Point
from smart_parking.spaces.validation import validate_parking_map


def parking_space_to_dict(space: ParkingSpace) -> dict[str, Any]:
    """Serialize one parking space to a JSON-compatible dict."""
    payload: dict[str, Any] = {
        "id": space.id,
        "label": space.label,
        "enabled": space.enabled,
        "polygon": [[point.x, point.y] for point in space.polygon],
    }
    if space.zone is not None:
        payload["zone"] = space.zone
    if space.metadata:
        payload["metadata"] = dict(space.metadata)
    return payload


def parking_map_to_dict(parking_map: ParkingMap) -> dict[str, Any]:
    """Serialize a parking map to a JSON-compatible dict."""
    return {
        "camera_id": parking_map.camera_id,
        "reference_width": parking_map.reference_width,
        "reference_height": parking_map.reference_height,
        "spaces": [parking_space_to_dict(space) for space in parking_map.spaces],
    }


def scale_point(point: Point, *, scale_x: float, scale_y: float) -> Point:
    """Scale a single point by independent X/Y factors."""
    return Point(point.x * scale_x, point.y * scale_y)


def scale_parking_map(
    parking_map: ParkingMap,
    *,
    target_width: int,
    target_height: int,
) -> ParkingMap:
    """Return a new map with polygons scaled to a different reference resolution.

    Raises ValueError when target dimensions are not positive.
    """
    if target_width <= 0 or target_height <= 0:
        msg = (
            "target_width and target_height must be positive integers; "
            f"got {target_width}x{target_height}."
        )
        raise ValueError(msg)

    if (
        target_width == parking_map.reference_width
        and target_height == parking_map.reference_height
    ):
        return parking_map

    scale_x = float(target_width) / float(parking_map.reference_width)
    scale_y = float(target_height) / float(parking_map.reference_height)

    scaled_spaces = tuple(
        ParkingSpace(
            id=space.id,
            label=space.label,
            polygon=tuple(scale_point(p, scale_x=scale_x, scale_y=scale_y) for p in space.polygon),
            zone=space.zone,
            enabled=space.enabled,
            metadata=dict(space.metadata),
        )
        for space in parking_map.spaces
    )
    scaled = ParkingMap(
        camera_id=parking_map.camera_id,
        reference_width=target_width,
        reference_height=target_height,
        spaces=scaled_spaces,
    )
    return validate_parking_map(scaled)


def save_parking_map(
    parking_map: ParkingMap,
    path: Path | str,
    *,
    validate: bool = True,
    indent: int = 2,
) -> Path:
    """Validate (optional) and write a parking map JSON file.

    Returns the resolved output path.
    """
    if validate:
        validate_parking_map(parking_map)

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = parking_map_to_dict(parking_map)
    out.write_text(json.dumps(payload, indent=indent) + "\n", encoding="utf-8")
    return out

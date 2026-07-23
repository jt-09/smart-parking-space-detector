"""Parking map serialization, scaling, and geometry validation."""

from smart_parking.spaces.serialize import (
    parking_map_to_dict,
    parking_space_to_dict,
    save_parking_map,
    scale_parking_map,
    scale_point,
)
from smart_parking.spaces.validation import (
    PolygonValidationError,
    is_self_intersecting,
    validate_parking_map,
    validate_space_geometry,
)

__all__ = [
    "PolygonValidationError",
    "is_self_intersecting",
    "parking_map_to_dict",
    "parking_space_to_dict",
    "save_parking_map",
    "scale_parking_map",
    "scale_point",
    "validate_parking_map",
    "validate_space_geometry",
]

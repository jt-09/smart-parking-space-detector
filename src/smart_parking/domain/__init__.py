"""Core domain types for parking occupancy detection.

These models are intentionally free of OpenCV and Ultralytics imports so that
geometry, state, and persistence layers stay portable.
"""

from smart_parking.domain.events import EventType, OccupancyEvent
from smart_parking.domain.parking import (
    BoundingBox,
    Detection,
    ParkingMap,
    ParkingSpace,
    Point,
)
from smart_parking.domain.state import (
    Clock,
    OccupancySnapshot,
    OccupancyState,
    SpaceOccupancy,
    SystemClock,
)

__all__ = [
    "BoundingBox",
    "Clock",
    "Detection",
    "EventType",
    "OccupancyEvent",
    "OccupancySnapshot",
    "OccupancyState",
    "ParkingMap",
    "ParkingSpace",
    "Point",
    "SpaceOccupancy",
    "SystemClock",
]

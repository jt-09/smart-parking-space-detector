"""Parking geometry and detection domain types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class Point:
    """2D image-plane coordinate in pixels."""

    x: float
    y: float

    def as_tuple(self) -> tuple[float, float]:
        return (self.x, self.y)


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """Axis-aligned detection box in pixel coordinates (xyxy)."""

    x1: float
    y1: float
    x2: float
    y2: float

    def __post_init__(self) -> None:
        if self.x2 < self.x1 or self.y2 < self.y1:
            msg = (
                f"Invalid bounding box ({self.x1}, {self.y1}, {self.x2}, {self.y2}): "
                "x2 must be >= x1 and y2 must be >= y1."
            )
            raise ValueError(msg)

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def center(self) -> Point:
        return Point((self.x1 + self.x2) / 2.0, (self.y1 + self.y2) / 2.0)

    @property
    def bottom_center(self) -> Point:
        return Point((self.x1 + self.x2) / 2.0, self.y2)

    def as_xyxy(self) -> tuple[float, float, float, float]:
        return (self.x1, self.y1, self.x2, self.y2)


@dataclass(frozen=True, slots=True)
class Detection:
    """Normalized vehicle detection independent of the detector backend."""

    bbox: BoundingBox
    confidence: float
    class_id: int
    class_name: str
    track_id: str | None = None
    frame_index: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            msg = f"Detection confidence must be in [0, 1], got {self.confidence}."
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class ParkingSpace:
    """A manually configured parking bay polygon."""

    id: str
    label: str
    polygon: tuple[Point, ...]
    zone: str | None = None
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("Parking space id must be a non-empty string.")
        if len(self.polygon) < 3:
            msg = (
                f"Parking space '{self.id}' polygon needs at least 3 points, "
                f"got {len(self.polygon)}. Add more vertices in the parking map."
            )
            raise ValueError(msg)

    @property
    def area(self) -> float:
        """Absolute shoelace area in square pixels."""
        pts = self.polygon
        total = 0.0
        for i, point in enumerate(pts):
            nxt = pts[(i + 1) % len(pts)]
            total += point.x * nxt.y - nxt.x * point.y
        return abs(total) / 2.0


@dataclass(frozen=True, slots=True)
class ParkingMap:
    """Camera-scoped collection of parking spaces."""

    camera_id: str
    reference_width: int
    reference_height: int
    spaces: tuple[ParkingSpace, ...]

    def __post_init__(self) -> None:
        if self.reference_width <= 0 or self.reference_height <= 0:
            msg = (
                "Parking map reference_width and reference_height must be positive "
                f"integers; got {self.reference_width}x{self.reference_height}."
            )
            raise ValueError(msg)
        if not self.camera_id.strip():
            raise ValueError("Parking map camera_id must be a non-empty string.")

        seen: set[str] = set()
        for space in self.spaces:
            if space.id in seen:
                msg = (
                    f"Duplicate parking space id '{space.id}'. "
                    "Each space id must be unique within a parking map."
                )
                raise ValueError(msg)
            seen.add(space.id)

    def get(self, space_id: str) -> ParkingSpace:
        for space in self.spaces:
            if space.id == space_id:
                return space
        msg = f"Unknown parking space id '{space_id}'."
        raise KeyError(msg)

    @property
    def enabled_spaces(self) -> tuple[ParkingSpace, ...]:
        return tuple(space for space in self.spaces if space.enabled)

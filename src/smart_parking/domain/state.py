"""Occupancy state types and UTC clock abstraction."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable


class OccupancyState(StrEnum):
    """Stable and transitional occupancy states for a parking space."""

    AVAILABLE = "available"
    OCCUPIED = "occupied"
    UNKNOWN = "unknown"
    PENDING_OCCUPIED = "pending_occupied"
    PENDING_AVAILABLE = "pending_available"


@runtime_checkable
class Clock(Protocol):
    """Injectable clock so tests can freeze time without monkeypatching."""

    def now(self) -> datetime:
        """Return the current time as a timezone-aware UTC datetime."""


@dataclass(frozen=True, slots=True)
class SystemClock:
    """Wall-clock implementation that always returns UTC."""

    def now(self) -> datetime:
        return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class SpaceOccupancy:
    """Per-space occupancy summary at a point in time."""

    space_id: str
    state: OccupancyState
    confidence: float = 0.0
    track_id: str | None = None
    score: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            msg = f"Space occupancy confidence must be in [0, 1], got {self.confidence}."
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class OccupancySnapshot:
    """Aggregated occupancy counts for a camera frame or sample interval."""

    camera_id: str
    captured_at: datetime
    spaces: tuple[SpaceOccupancy, ...]
    frame_index: int | None = None
    run_id: str | None = None

    def __post_init__(self) -> None:
        if self.captured_at.tzinfo is None:
            raise ValueError("OccupancySnapshot.captured_at must be timezone-aware (UTC).")

    @property
    def available(self) -> int:
        return sum(1 for s in self.spaces if s.state == OccupancyState.AVAILABLE)

    @property
    def occupied(self) -> int:
        return sum(1 for s in self.spaces if s.state == OccupancyState.OCCUPIED)

    @property
    def unknown(self) -> int:
        return sum(
            1
            for s in self.spaces
            if s.state
            in {
                OccupancyState.UNKNOWN,
                OccupancyState.PENDING_OCCUPIED,
                OccupancyState.PENDING_AVAILABLE,
            }
        )

    @property
    def occupancy_percent(self) -> float:
        """Occupied / (available + occupied) * 100; unknown excluded by default."""
        denominator = self.available + self.occupied
        if denominator == 0:
            return 0.0
        return (self.occupied / denominator) * 100.0

"""Occupancy transition events."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from smart_parking.domain.state import OccupancyState


class EventType(StrEnum):
    """Meaningful occupancy transitions persisted for analytics."""

    OCCUPIED = "occupied"
    VACATED = "vacated"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class OccupancyEvent:
    """A confirmed occupancy state transition for a parking space."""

    id: UUID
    run_id: UUID
    space_id: str
    event_type: EventType
    previous_state: OccupancyState
    new_state: OccupancyState
    confirmed_at: datetime
    confidence: float
    idempotency_key: str
    raw_transition_started_at: datetime | None = None
    track_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.confirmed_at.tzinfo is None:
            raise ValueError("OccupancyEvent.confirmed_at must be timezone-aware (UTC).")
        if (
            self.raw_transition_started_at is not None
            and self.raw_transition_started_at.tzinfo is None
        ):
            raise ValueError(
                "OccupancyEvent.raw_transition_started_at must be timezone-aware (UTC)."
            )
        if not 0.0 <= self.confidence <= 1.0:
            msg = f"OccupancyEvent confidence must be in [0, 1], got {self.confidence}."
            raise ValueError(msg)
        if not self.idempotency_key.strip():
            raise ValueError("OccupancyEvent.idempotency_key must be a non-empty string.")
        if not self.space_id.strip():
            raise ValueError("OccupancyEvent.space_id must be a non-empty string.")

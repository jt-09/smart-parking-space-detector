"""Confirmed-transition recording with optional SQLite persistence."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from smart_parking.domain.events import OccupancyEvent
from smart_parking.domain.state import OccupancySnapshot, OccupancyState
from smart_parking.persistence.repository import (
    CONFIRMED_STATES,
    EventRepository,
    build_idempotency_key,
    event_type_for_transition,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class TransitionRecorder:
    """Derive confirmed occupancy events from successive snapshots.

    Only AVAILABLE / OCCUPIED / UNKNOWN states are treated as confirmed.
    Pending states are ignored until they resolve. Duplicate snapshots that
    repeat the same confirmed state do not emit another event.
    """

    run_id: str
    _last_confirmed: dict[str, OccupancyState] = field(default_factory=dict)

    def observe(self, snapshot: OccupancySnapshot) -> list[OccupancyEvent]:
        """Return newly confirmed transitions implied by ``snapshot``."""
        events: list[OccupancyEvent] = []
        for space in snapshot.spaces:
            if space.state not in CONFIRMED_STATES:
                continue
            previous = self._last_confirmed.get(space.space_id)
            if previous is None:
                # First observation: seed without emitting (cold start / UNKNOWN).
                self._last_confirmed[space.space_id] = space.state
                continue
            if previous == space.state:
                continue

            event_type = event_type_for_transition(previous, space.state)
            if event_type is None:
                self._last_confirmed[space.space_id] = space.state
                continue

            confirmed_at = snapshot.captured_at
            try:
                run_uuid = UUID(self.run_id)
            except ValueError:
                run_uuid = uuid4()

            key = build_idempotency_key(
                run_id=self.run_id,
                space_id=space.space_id,
                event_type=event_type,
                previous_state=previous,
                new_state=space.state,
                confirmed_at=confirmed_at,
            )
            events.append(
                OccupancyEvent(
                    id=uuid4(),
                    run_id=run_uuid,
                    space_id=space.space_id,
                    event_type=event_type,
                    previous_state=previous,
                    new_state=space.state,
                    confirmed_at=confirmed_at,
                    confidence=space.confidence,
                    idempotency_key=key,
                    track_id=space.track_id,
                    metadata={
                        "frame_index": snapshot.frame_index,
                        "camera_id": snapshot.camera_id,
                    },
                )
            )
            self._last_confirmed[space.space_id] = space.state
        return events


@dataclass(slots=True)
class EventService:
    """Persist confirmed transitions and optional interval snapshots."""

    repository: EventRepository
    run_id: str
    snapshot_interval_seconds: float = 5.0
    _recorder: TransitionRecorder | None = None
    _last_snapshot_at: datetime | None = None
    _persisted_events: int = 0
    _duplicate_events: int = 0

    def __post_init__(self) -> None:
        if self._recorder is None:
            self._recorder = TransitionRecorder(run_id=self.run_id)

    @property
    def persisted_events(self) -> int:
        return self._persisted_events

    @property
    def duplicate_events(self) -> int:
        return self._duplicate_events

    def handle_snapshot(self, snapshot: OccupancySnapshot) -> list[OccupancyEvent]:
        """Record confirmed transitions; optionally persist an interval snapshot."""
        assert self._recorder is not None
        events = self._recorder.observe(snapshot)
        for event in events:
            inserted = self.repository.persist_event(event)
            if inserted:
                self._persisted_events += 1
            else:
                self._duplicate_events += 1
                logger.debug(
                    "Skipped duplicate occupancy event key=%s",
                    event.idempotency_key,
                )

        if self.snapshot_interval_seconds > 0:
            should_write = self._last_snapshot_at is None or (
                snapshot.captured_at - self._last_snapshot_at
            ) >= timedelta(seconds=self.snapshot_interval_seconds)
            if should_write:
                try:
                    self.repository.persist_snapshot(snapshot)
                    self._last_snapshot_at = snapshot.captured_at
                except Exception:
                    logger.exception("Failed to persist occupancy snapshot.")

        return events

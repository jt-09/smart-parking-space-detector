"""Repository interfaces and SQLAlchemy implementations for event persistence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from smart_parking.domain.events import EventType, OccupancyEvent
from smart_parking.domain.parking import ParkingMap
from smart_parking.domain.state import OccupancySnapshot, OccupancyState
from smart_parking.persistence.models import (
    OccupancyEventRow,
    OccupancySnapshotRow,
    ParkingSpaceRow,
    ProcessingRunRow,
)

CONFIRMED_STATES = frozenset(
    {
        OccupancyState.AVAILABLE,
        OccupancyState.OCCUPIED,
        OccupancyState.UNKNOWN,
    }
)


def _ensure_utc(value: datetime) -> datetime:
    """SQLite often returns naive datetimes; treat them as UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _ensure_utc_optional(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return _ensure_utc(value)


@dataclass(frozen=True, slots=True)
class ProcessingRunRecord:
    """Domain-facing view of a processing run row."""

    id: str
    camera_id: str
    source_fingerprint: str
    started_at: datetime
    ended_at: datetime | None
    status: str
    model_name: str
    model_version: str | None
    frames_read: int
    frames_processed: int
    error_message: str | None


@runtime_checkable
class EventRepository(Protocol):
    """Persistence contract used by the pipeline and analytics layers."""

    def start_run(
        self,
        *,
        run_id: str,
        camera_id: str,
        source_fingerprint: str,
        started_at: datetime,
        model_name: str,
        model_version: str | None = None,
        config_json: str = "{}",
    ) -> ProcessingRunRecord: ...

    def complete_run(
        self,
        run_id: str,
        *,
        ended_at: datetime,
        frames_read: int,
        frames_processed: int,
    ) -> None: ...

    def fail_run(
        self,
        run_id: str,
        *,
        ended_at: datetime,
        error_message: str,
        frames_read: int = 0,
        frames_processed: int = 0,
    ) -> None: ...

    def interrupt_run(
        self,
        run_id: str,
        *,
        ended_at: datetime,
        frames_read: int,
        frames_processed: int,
    ) -> None: ...

    def sync_parking_spaces(self, parking_map: ParkingMap, *, now: datetime) -> None: ...

    def persist_event(self, event: OccupancyEvent) -> bool:
        """Insert an event. Returns False when the idempotency key already exists."""
        ...

    def persist_snapshot(self, snapshot: OccupancySnapshot) -> None: ...

    def list_events(
        self,
        *,
        space_id: str | None = None,
        run_id: str | None = None,
        after: datetime | None = None,
        before: datetime | None = None,
        limit: int | None = None,
    ) -> list[OccupancyEvent]: ...

    def purge_before(self, before: datetime) -> int:
        """Delete occupancy events confirmed before ``before``. Returns deleted count."""
        ...

    def get_run(self, run_id: str) -> ProcessingRunRecord | None: ...

    def list_runs(self, *, limit: int | None = None) -> list[ProcessingRunRecord]: ...


def event_type_for_transition(
    previous: OccupancyState,
    new: OccupancyState,
) -> EventType | None:
    """Map a confirmed state change to an analytics event type, or None if not persisted."""
    if new == OccupancyState.OCCUPIED:
        return EventType.OCCUPIED
    if new == OccupancyState.AVAILABLE and previous == OccupancyState.OCCUPIED:
        return EventType.VACATED
    if new == OccupancyState.UNKNOWN and previous != OccupancyState.UNKNOWN:
        return EventType.UNKNOWN
    return None


def build_idempotency_key(
    *,
    run_id: str,
    space_id: str,
    event_type: EventType,
    previous_state: OccupancyState,
    new_state: OccupancyState,
    confirmed_at: datetime,
) -> str:
    """Stable unique key so duplicate pipeline callbacks cannot insert twice."""
    stamp = confirmed_at.astimezone().isoformat()
    return (
        f"{run_id}:{space_id}:{event_type.value}:{previous_state.value}:{new_state.value}:{stamp}"
    )


def _row_to_event(row: OccupancyEventRow) -> OccupancyEvent:
    metadata: dict[str, object]
    try:
        loaded = json.loads(row.metadata_json)
        metadata = loaded if isinstance(loaded, dict) else {}
    except json.JSONDecodeError:
        metadata = {}
    return OccupancyEvent(
        id=UUID(row.id),
        run_id=UUID(row.run_id),
        space_id=row.space_id,
        event_type=EventType(row.event_type),
        previous_state=OccupancyState(row.previous_state),
        new_state=OccupancyState(row.new_state),
        confirmed_at=_ensure_utc(row.confirmed_at),
        confidence=row.confidence,
        idempotency_key=row.idempotency_key,
        raw_transition_started_at=_ensure_utc_optional(row.raw_transition_started_at),
        track_id=row.track_id,
        metadata=metadata,
    )


def _row_to_run(row: ProcessingRunRow) -> ProcessingRunRecord:
    return ProcessingRunRecord(
        id=row.id,
        camera_id=row.camera_id,
        source_fingerprint=row.source_fingerprint,
        started_at=_ensure_utc(row.started_at),
        ended_at=_ensure_utc_optional(row.ended_at),
        status=row.status,
        model_name=row.model_name,
        model_version=row.model_version,
        frames_read=row.frames_read,
        frames_processed=row.frames_processed,
        error_message=row.error_message,
    )


class SqlAlchemyEventRepository:
    """SQLAlchemy-backed event repository using short-lived sessions."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def start_run(
        self,
        *,
        run_id: str,
        camera_id: str,
        source_fingerprint: str,
        started_at: datetime,
        model_name: str,
        model_version: str | None = None,
        config_json: str = "{}",
    ) -> ProcessingRunRecord:
        with self._session_factory() as session:
            row = ProcessingRunRow(
                id=run_id,
                camera_id=camera_id,
                source_fingerprint=source_fingerprint,
                started_at=started_at,
                status="running",
                model_name=model_name,
                model_version=model_version,
                config_json=config_json,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return _row_to_run(row)

    def complete_run(
        self,
        run_id: str,
        *,
        ended_at: datetime,
        frames_read: int,
        frames_processed: int,
    ) -> None:
        self._finish_run(
            run_id,
            status="completed",
            ended_at=ended_at,
            frames_read=frames_read,
            frames_processed=frames_processed,
        )

    def fail_run(
        self,
        run_id: str,
        *,
        ended_at: datetime,
        error_message: str,
        frames_read: int = 0,
        frames_processed: int = 0,
    ) -> None:
        self._finish_run(
            run_id,
            status="failed",
            ended_at=ended_at,
            frames_read=frames_read,
            frames_processed=frames_processed,
            error_message=error_message,
        )

    def interrupt_run(
        self,
        run_id: str,
        *,
        ended_at: datetime,
        frames_read: int,
        frames_processed: int,
    ) -> None:
        self._finish_run(
            run_id,
            status="interrupted",
            ended_at=ended_at,
            frames_read=frames_read,
            frames_processed=frames_processed,
        )

    def _finish_run(
        self,
        run_id: str,
        *,
        status: str,
        ended_at: datetime,
        frames_read: int,
        frames_processed: int,
        error_message: str | None = None,
    ) -> None:
        with self._session_factory() as session:
            row = session.get(ProcessingRunRow, run_id)
            if row is None:
                msg = f"Unknown processing run id '{run_id}'."
                raise KeyError(msg)
            row.status = status
            row.ended_at = ended_at
            row.frames_read = frames_read
            row.frames_processed = frames_processed
            if error_message is not None:
                row.error_message = error_message
            session.commit()

    def sync_parking_spaces(self, parking_map: ParkingMap, *, now: datetime) -> None:
        with self._session_factory() as session:
            for space in parking_map.spaces:
                polygon_json = json.dumps([[p.x, p.y] for p in space.polygon])
                metadata_json = json.dumps(space.metadata)
                existing = session.get(ParkingSpaceRow, space.id)
                if existing is None:
                    session.add(
                        ParkingSpaceRow(
                            id=space.id,
                            camera_id=parking_map.camera_id,
                            label=space.label,
                            polygon_json=polygon_json,
                            zone=space.zone,
                            enabled=space.enabled,
                            metadata_json=metadata_json,
                            created_at=now,
                            updated_at=now,
                        )
                    )
                else:
                    existing.camera_id = parking_map.camera_id
                    existing.label = space.label
                    existing.polygon_json = polygon_json
                    existing.zone = space.zone
                    existing.enabled = space.enabled
                    existing.metadata_json = metadata_json
                    existing.updated_at = now
            session.commit()

    def persist_event(self, event: OccupancyEvent) -> bool:
        row = OccupancyEventRow(
            id=str(event.id),
            run_id=str(event.run_id),
            space_id=event.space_id,
            event_type=event.event_type.value,
            previous_state=event.previous_state.value,
            new_state=event.new_state.value,
            confirmed_at=event.confirmed_at,
            raw_transition_started_at=event.raw_transition_started_at,
            confidence=event.confidence,
            track_id=event.track_id,
            metadata_json=json.dumps(event.metadata),
            idempotency_key=event.idempotency_key,
        )
        with self._session_factory() as session:
            session.add(row)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                return False
            return True

    def persist_snapshot(self, snapshot: OccupancySnapshot) -> None:
        if snapshot.run_id is None:
            raise ValueError("OccupancySnapshot.run_id is required to persist a snapshot.")
        spaces_payload = [
            {
                "space_id": s.space_id,
                "state": s.state.value,
                "confidence": s.confidence,
                "track_id": s.track_id,
                "score": s.score,
            }
            for s in snapshot.spaces
        ]
        row = OccupancySnapshotRow(
            id=str(uuid4()),
            run_id=snapshot.run_id,
            captured_at=snapshot.captured_at,
            available=snapshot.available,
            occupied=snapshot.occupied,
            unknown=snapshot.unknown,
            occupancy_percent=snapshot.occupancy_percent,
            spaces_json=json.dumps(spaces_payload),
        )
        with self._session_factory() as session:
            session.add(row)
            session.commit()

    def list_events(
        self,
        *,
        space_id: str | None = None,
        run_id: str | None = None,
        after: datetime | None = None,
        before: datetime | None = None,
        limit: int | None = None,
    ) -> list[OccupancyEvent]:
        with self._session_factory() as session:
            stmt = select(OccupancyEventRow).order_by(OccupancyEventRow.confirmed_at.asc())
            if space_id is not None:
                stmt = stmt.where(OccupancyEventRow.space_id == space_id)
            if run_id is not None:
                stmt = stmt.where(OccupancyEventRow.run_id == run_id)
            if after is not None:
                stmt = stmt.where(OccupancyEventRow.confirmed_at >= after)
            if before is not None:
                stmt = stmt.where(OccupancyEventRow.confirmed_at < before)
            if limit is not None:
                stmt = stmt.limit(limit)
            rows = session.scalars(stmt).all()
            return [_row_to_event(row) for row in rows]

    def purge_before(self, before: datetime) -> int:
        with self._session_factory() as session:
            result = session.execute(
                delete(OccupancyEventRow).where(OccupancyEventRow.confirmed_at < before)
            )
            session.commit()
            # SQLAlchemy CursorResult exposes rowcount; cast for mypy.
            return int(getattr(result, "rowcount", 0) or 0)

    def get_run(self, run_id: str) -> ProcessingRunRecord | None:
        with self._session_factory() as session:
            row = session.get(ProcessingRunRow, run_id)
            if row is None:
                return None
            return _row_to_run(row)

    def list_runs(self, *, limit: int | None = None) -> list[ProcessingRunRecord]:
        with self._session_factory() as session:
            stmt = select(ProcessingRunRow).order_by(ProcessingRunRow.started_at.desc())
            if limit is not None:
                stmt = stmt.limit(limit)
            rows = session.scalars(stmt).all()
            return [_row_to_run(row) for row in rows]

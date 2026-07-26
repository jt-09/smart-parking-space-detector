"""SQLite event persistence and confirmed-transition recording."""

from smart_parking.persistence.db import (
    create_db_engine,
    init_schema,
    make_session_factory,
    migrate,
    normalize_database_url,
    session_scope,
)
from smart_parking.persistence.events import EventService, TransitionRecorder
from smart_parking.persistence.models import (
    Base,
    OccupancyEventRow,
    OccupancySnapshotRow,
    ParkingSpaceRow,
    ProcessingRunRow,
)
from smart_parking.persistence.repository import (
    EventRepository,
    ProcessingRunRecord,
    SqlAlchemyEventRepository,
    build_idempotency_key,
    event_type_for_transition,
)

__all__ = [
    "Base",
    "EventRepository",
    "EventService",
    "OccupancyEventRow",
    "OccupancySnapshotRow",
    "ParkingSpaceRow",
    "ProcessingRunRecord",
    "ProcessingRunRow",
    "SqlAlchemyEventRepository",
    "TransitionRecorder",
    "build_idempotency_key",
    "create_db_engine",
    "event_type_for_transition",
    "init_schema",
    "make_session_factory",
    "migrate",
    "normalize_database_url",
    "session_scope",
]

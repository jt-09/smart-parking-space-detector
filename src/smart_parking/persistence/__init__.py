"""SQLite event persistence, analytics, and confirmed-transition recording."""

from smart_parking.persistence.analytics import (
    HourlyOccupancyBucket,
    ParkingDuration,
    TurnoverSummary,
    calculate_durations,
    calculate_turnover,
    hourly_occupancy_summary,
    load_and_analyze,
    mean_duration_seconds,
    retention_cutoff,
)
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
    "HourlyOccupancyBucket",
    "OccupancyEventRow",
    "OccupancySnapshotRow",
    "ParkingDuration",
    "ParkingSpaceRow",
    "ProcessingRunRecord",
    "ProcessingRunRow",
    "SqlAlchemyEventRepository",
    "TransitionRecorder",
    "TurnoverSummary",
    "build_idempotency_key",
    "calculate_durations",
    "calculate_turnover",
    "create_db_engine",
    "event_type_for_transition",
    "hourly_occupancy_summary",
    "init_schema",
    "load_and_analyze",
    "make_session_factory",
    "mean_duration_seconds",
    "migrate",
    "normalize_database_url",
    "retention_cutoff",
    "session_scope",
]

"""SQLite event persistence package (schema layer)."""

from smart_parking.persistence.db import (
    create_db_engine,
    init_schema,
    make_session_factory,
    migrate,
    normalize_database_url,
    session_scope,
)
from smart_parking.persistence.models import (
    Base,
    OccupancyEventRow,
    OccupancySnapshotRow,
    ParkingSpaceRow,
    ProcessingRunRow,
)

__all__ = [
    "Base",
    "OccupancyEventRow",
    "OccupancySnapshotRow",
    "ParkingSpaceRow",
    "ProcessingRunRow",
    "create_db_engine",
    "init_schema",
    "make_session_factory",
    "migrate",
    "normalize_database_url",
    "session_scope",
]

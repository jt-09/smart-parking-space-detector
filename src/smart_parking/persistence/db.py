"""Database engine helpers and schema initialization (migrations-lite)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from smart_parking.persistence.models import Base


def normalize_database_url(database_url: str) -> str:
    """Normalize SQLite URLs and ensure parent directories exist for file DBs."""
    url = database_url.strip()
    if url.startswith("sqlite:///"):
        path_part = url.removeprefix("sqlite:///")
        if path_part not in {":memory:", ""} and not path_part.startswith("/"):
            # Relative file path — create parent dirs so create_all / connect succeed.
            Path(path_part).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
    return url


def create_db_engine(database_url: str, *, echo: bool = False) -> Engine:
    """Create a SQLAlchemy engine with SQLite foreign-key enforcement."""
    url = normalize_database_url(database_url)
    connect_args: dict[str, object] = {}
    if url.startswith("sqlite"):
        # Needed for multi-threaded CLI / pipeline usage of the same connection.
        connect_args["check_same_thread"] = False
    engine = create_engine(url, echo=echo, future=True, connect_args=connect_args)

    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection: object, _connection_record: object) -> None:
            cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def init_schema(engine: Engine) -> None:
    """Create all tables if they do not already exist (v1 migrations-lite)."""
    Base.metadata.create_all(engine)


def migrate(database_url: str) -> Engine:
    """Ensure the schema exists for ``database_url`` and return the engine."""
    engine = create_db_engine(database_url)
    init_schema(engine)
    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return a session factory bound to ``engine``."""
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    """Provide a transactional scope around a series of operations."""
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

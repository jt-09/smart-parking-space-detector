"""SQLAlchemy ORM models for processing runs and occupancy events."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid_str() -> str:
    return str(uuid4())


class Base(DeclarativeBase):
    """Declarative base for Smart Parking persistence tables."""


class ProcessingRunRow(Base):
    """One pipeline execution (video file, webcam session, or stream)."""

    __tablename__ = "processing_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    camera_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_fingerprint: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    model_name: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    model_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    config_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    frames_read: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    frames_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    events: Mapped[list[OccupancyEventRow]] = relationship(back_populates="run")
    snapshots: Mapped[list[OccupancySnapshotRow]] = relationship(back_populates="run")


class ParkingSpaceRow(Base):
    """Optional synced copy of configured parking spaces for a camera."""

    __tablename__ = "parking_spaces"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    camera_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(256), nullable=False)
    polygon_json: Mapped[str] = mapped_column(Text, nullable=False)
    zone: Mapped[str | None] = mapped_column(String(128), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OccupancyEventRow(Base):
    """Confirmed occupancy transition persisted for analytics."""

    __tablename__ = "occupancy_events"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_occupancy_events_idempotency"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("processing_runs.id"), nullable=False, index=True
    )
    space_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    previous_state: Mapped[str] = mapped_column(String(32), nullable=False)
    new_state: Mapped[str] = mapped_column(String(32), nullable=False)
    confirmed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    raw_transition_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    track_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    idempotency_key: Mapped[str] = mapped_column(String(512), nullable=False)

    run: Mapped[ProcessingRunRow] = relationship(back_populates="events")


class OccupancySnapshotRow(Base):
    """Optional interval snapshot of aggregate occupancy counts."""

    __tablename__ = "occupancy_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("processing_runs.id"), nullable=False, index=True
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    available: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    occupied: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unknown: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    occupancy_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    spaces_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    run: Mapped[ProcessingRunRow] = relationship(back_populates="snapshots")

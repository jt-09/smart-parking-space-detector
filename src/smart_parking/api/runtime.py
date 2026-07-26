"""In-memory runtime state shared by API routes and the dashboard."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock

from smart_parking.config.models import Settings
from smart_parking.domain.state import OccupancySnapshot, OccupancyState, SpaceOccupancy
from smart_parking.persistence.repository import EventRepository


@dataclass(slots=True)
class SourceModelStatus:
    """Configured source / model metadata exposed via status endpoints."""

    camera_id: str
    source: str
    model_name: str
    model_device: str
    max_frame_age_seconds: float
    persistence_enabled: bool
    last_frame_at: datetime | None = None

    def is_stale(self, *, now: datetime | None = None) -> bool:
        """True when no frame has arrived or the latest frame exceeds max age."""
        if self.last_frame_at is None:
            return True
        clock = now if now is not None else datetime.now(UTC)
        if clock.tzinfo is None:
            clock = clock.replace(tzinfo=UTC)
        age = (clock - self.last_frame_at.astimezone(UTC)).total_seconds()
        return age > self.max_frame_age_seconds


@dataclass
class StatusStore:
    """Thread-safe holder for the latest occupancy snapshot and source status."""

    source: SourceModelStatus
    snapshot: OccupancySnapshot | None = None
    _lock: Lock = field(default_factory=Lock, repr=False)

    def get_snapshot(self) -> OccupancySnapshot | None:
        with self._lock:
            return self.snapshot

    def set_snapshot(self, snapshot: OccupancySnapshot) -> None:
        with self._lock:
            self.snapshot = snapshot
            self.source.last_frame_at = snapshot.captured_at

    def get_source(self) -> SourceModelStatus:
        with self._lock:
            return SourceModelStatus(
                camera_id=self.source.camera_id,
                source=self.source.source,
                model_name=self.source.model_name,
                model_device=self.source.model_device,
                max_frame_age_seconds=self.source.max_frame_age_seconds,
                persistence_enabled=self.source.persistence_enabled,
                last_frame_at=self.source.last_frame_at,
            )

    def space_by_id(self, space_id: str) -> SpaceOccupancy | None:
        snapshot = self.get_snapshot()
        if snapshot is None:
            return None
        for space in snapshot.spaces:
            if space.space_id == space_id:
                return space
        return None


@dataclass(slots=True)
class AppContext:
    """Dependencies injected into FastAPI route handlers."""

    settings: Settings
    store: StatusStore
    repository: EventRepository | None = None


def source_status_from_settings(settings: Settings) -> SourceModelStatus:
    """Build a source/model status block from application settings."""
    return SourceModelStatus(
        camera_id=settings.camera.id,
        source=settings.camera.source,
        model_name=settings.model.name,
        model_device=settings.model.device,
        max_frame_age_seconds=settings.camera.max_frame_age_seconds,
        persistence_enabled=settings.persistence.enabled,
    )


def empty_snapshot(*, camera_id: str, captured_at: datetime | None = None) -> OccupancySnapshot:
    """Placeholder snapshot used when no pipeline has published state yet."""
    stamp = captured_at if captured_at is not None else datetime.now(UTC)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    return OccupancySnapshot(camera_id=camera_id, captured_at=stamp, spaces=())


def confirmed_space_state(state: OccupancyState) -> OccupancyState:
    """Collapse pending states to unknown for operator-facing summaries."""
    if state in {OccupancyState.PENDING_OCCUPIED, OccupancyState.PENDING_AVAILABLE}:
        return OccupancyState.UNKNOWN
    return state

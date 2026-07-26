"""HTTP route handlers for health, status, events, analytics, and runs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from smart_parking import __version__
from smart_parking.api.dependencies import AppContextDep, RepositoryDep, StatusStoreDep
from smart_parking.api.runtime import StatusStore, confirmed_space_state
from smart_parking.api.schemas import (
    EventListResponse,
    EventResponse,
    HealthResponse,
    HourlyOccupancyResponse,
    OccupancyAnalyticsResponse,
    RunListResponse,
    RunResponse,
    SourceStatusResponse,
    SpaceStatusResponse,
    StatusResponse,
    TurnoverAnalyticsResponse,
)
from smart_parking.domain.events import OccupancyEvent
from smart_parking.domain.state import OccupancySnapshot, OccupancyState, SpaceOccupancy
from smart_parking.persistence.analytics import (
    calculate_durations,
    calculate_turnover,
    hourly_occupancy_summary,
    mean_duration_seconds,
)
from smart_parking.persistence.repository import ProcessingRunRecord

router = APIRouter()
api_router = APIRouter(prefix="/api/v1")


def _parse_optional_datetime(value: str | None, *, field_name: str) -> datetime | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        raise HTTPException(
            status_code=422,
            detail=f"{field_name} must be a non-empty ISO-8601 timestamp when provided.",
        )
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid {field_name}: expected ISO-8601 datetime, got '{value}'.",
        ) from exc
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _space_response(space: SpaceOccupancy) -> SpaceStatusResponse:
    pending = space.state in {
        OccupancyState.PENDING_OCCUPIED,
        OccupancyState.PENDING_AVAILABLE,
    }
    display = confirmed_space_state(space.state)
    return SpaceStatusResponse(
        space_id=space.space_id,
        state=str(display),
        confidence=space.confidence,
        track_id=space.track_id,
        score=space.score,
        is_unknown=display == OccupancyState.UNKNOWN,
        is_pending=pending,
    )


def _source_response(store: StatusStore, *, now: datetime | None = None) -> SourceStatusResponse:
    source = store.get_source()
    return SourceStatusResponse(
        camera_id=source.camera_id,
        source=source.source,
        model_name=source.model_name,
        model_device=source.model_device,
        last_frame_at=source.last_frame_at,
        stale=source.is_stale(now=now),
        max_frame_age_seconds=source.max_frame_age_seconds,
        persistence_enabled=source.persistence_enabled,
    )


def _status_from_snapshot(
    snapshot: OccupancySnapshot | None,
    store: StatusStore,
    *,
    camera_id: str,
) -> StatusResponse:
    source = _source_response(store)
    if snapshot is None:
        return StatusResponse(
            camera_id=camera_id,
            captured_at=None,
            total_spaces=0,
            available=0,
            occupied=0,
            unknown=0,
            occupancy_percent=0.0,
            stale=True,
            source=source,
            spaces=[],
        )
    spaces = [_space_response(space) for space in snapshot.spaces]
    return StatusResponse(
        camera_id=snapshot.camera_id,
        captured_at=snapshot.captured_at,
        total_spaces=len(snapshot.spaces),
        available=snapshot.available,
        occupied=snapshot.occupied,
        unknown=snapshot.unknown,
        occupancy_percent=snapshot.occupancy_percent,
        stale=source.stale,
        source=source,
        spaces=spaces,
    )


def _event_response(event: OccupancyEvent) -> EventResponse:
    return EventResponse(
        id=event.id,
        run_id=event.run_id,
        space_id=event.space_id,
        event_type=str(event.event_type),
        previous_state=str(event.previous_state),
        new_state=str(event.new_state),
        confirmed_at=event.confirmed_at,
        confidence=event.confidence,
        track_id=event.track_id,
        idempotency_key=event.idempotency_key,
        metadata=dict(event.metadata),
    )


def _run_response(run: ProcessingRunRecord) -> RunResponse:
    return RunResponse(
        id=run.id,
        camera_id=run.camera_id,
        source_fingerprint=run.source_fingerprint,
        started_at=run.started_at,
        ended_at=run.ended_at,
        status=run.status,
        model_name=run.model_name,
        model_version=run.model_version,
        frames_read=run.frames_read,
        frames_processed=run.frames_processed,
        error_message=run.error_message,
    )


@router.get("/health", response_model=HealthResponse, tags=["health"])
@api_router.get("/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    """Liveness probe available at `/health` and `/api/v1/health`."""
    return HealthResponse(status="ok", version=__version__)


@api_router.get("/status", response_model=StatusResponse, tags=["status"])
def get_status(context: AppContextDep, store: StatusStoreDep) -> StatusResponse:
    """Return current occupancy counts and source freshness."""
    return _status_from_snapshot(
        store.get_snapshot(),
        store,
        camera_id=context.settings.camera.id,
    )


@api_router.get("/spaces", response_model=list[SpaceStatusResponse], tags=["spaces"])
def list_spaces(store: StatusStoreDep) -> list[SpaceStatusResponse]:
    """List per-space occupancy from the latest snapshot."""
    snapshot = store.get_snapshot()
    if snapshot is None:
        return []
    return [_space_response(space) for space in snapshot.spaces]


@api_router.get("/spaces/{space_id}", response_model=SpaceStatusResponse, tags=["spaces"])
def get_space(space_id: str, store: StatusStoreDep) -> SpaceStatusResponse:
    """Return one space from the latest snapshot."""
    space = store.space_by_id(space_id)
    if space is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Space '{space_id}' was not found in the current snapshot.",
        )
    return _space_response(space)


@api_router.get("/events", response_model=EventListResponse, tags=["events"])
def list_events(
    repository: RepositoryDep,
    space_id: Annotated[str | None, Query(description="Filter by parking space id")] = None,
    run_id: Annotated[str | None, Query(description="Filter by processing run id")] = None,
    after: Annotated[str | None, Query(description="ISO-8601 lower bound (inclusive)")] = None,
    before: Annotated[str | None, Query(description="ISO-8601 upper bound (exclusive)")] = None,
    limit: Annotated[
        int | None,
        Query(ge=1, le=10_000, description="Maximum number of events to return"),
    ] = 100,
) -> EventListResponse:
    """List persisted occupancy events (requires persistence)."""
    after_dt = _parse_optional_datetime(after, field_name="after")
    before_dt = _parse_optional_datetime(before, field_name="before")
    events = repository.list_events(
        space_id=space_id,
        run_id=run_id,
        after=after_dt,
        before=before_dt,
        limit=limit,
    )
    # list_events returns ascending; expose newest-first for operators.
    events = list(reversed(events))
    return EventListResponse(count=len(events), events=[_event_response(e) for e in events])


@api_router.get(
    "/analytics/occupancy",
    response_model=OccupancyAnalyticsResponse,
    tags=["analytics"],
)
def analytics_occupancy(
    repository: RepositoryDep,
    space_id: Annotated[str | None, Query()] = None,
    after: Annotated[str | None, Query()] = None,
    before: Annotated[str | None, Query()] = None,
) -> OccupancyAnalyticsResponse:
    """Hourly occupancy buckets and mean stay duration."""
    after_dt = _parse_optional_datetime(after, field_name="after")
    before_dt = _parse_optional_datetime(before, field_name="before")
    events = repository.list_events(space_id=space_id, after=after_dt, before=before_dt)
    durations = calculate_durations(events, space_id=space_id)
    buckets = hourly_occupancy_summary(events, space_id=space_id)
    completed = [d for d in durations if not d.still_occupied]
    still = [d for d in durations if d.still_occupied]
    return OccupancyAnalyticsResponse(
        space_id=space_id,
        after=after_dt,
        before=before_dt,
        buckets=[
            HourlyOccupancyResponse(
                hour_start=b.hour_start,
                occupied_events=b.occupied_events,
                vacated_events=b.vacated_events,
                unknown_events=b.unknown_events,
            )
            for b in buckets
        ],
        mean_duration_seconds=mean_duration_seconds(durations, completed_only=True),
        completed_stays=len(completed),
        still_occupied_stays=len(still),
    )


@api_router.get(
    "/analytics/turnover",
    response_model=TurnoverAnalyticsResponse,
    tags=["analytics"],
)
def analytics_turnover(
    repository: RepositoryDep,
    space_id: Annotated[str | None, Query()] = None,
    after: Annotated[str | None, Query()] = None,
    before: Annotated[str | None, Query()] = None,
) -> TurnoverAnalyticsResponse:
    """Occupied / vacated / unknown event counts for a window."""
    after_dt = _parse_optional_datetime(after, field_name="after")
    before_dt = _parse_optional_datetime(before, field_name="before")
    events = repository.list_events(space_id=space_id, after=after_dt, before=before_dt)
    summary = calculate_turnover(events, space_id=space_id)
    return TurnoverAnalyticsResponse(
        space_id=summary.space_id,
        after=after_dt,
        before=before_dt,
        occupied_count=summary.occupied_count,
        vacated_count=summary.vacated_count,
        unknown_count=summary.unknown_count,
    )


@api_router.get("/runs", response_model=RunListResponse, tags=["runs"])
def list_runs(
    repository: RepositoryDep,
    limit: Annotated[int | None, Query(ge=1, le=10_000)] = 50,
) -> RunListResponse:
    """List recent processing runs (newest first)."""
    runs = repository.list_runs(limit=limit)
    return RunListResponse(count=len(runs), runs=[_run_response(r) for r in runs])


@api_router.get("/runs/{run_id}", response_model=RunResponse, tags=["runs"])
def get_run(run_id: str, repository: RepositoryDep) -> RunResponse:
    """Return one processing run by id."""
    run = repository.get_run(run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Processing run '{run_id}' was not found.",
        )
    return _run_response(run)

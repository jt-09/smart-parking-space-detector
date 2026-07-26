"""Pydantic response schemas for the status API."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    """Liveness probe payload."""

    status: str = "ok"
    version: str


class SpaceStatusResponse(BaseModel):
    """Per-space occupancy row."""

    model_config = ConfigDict(from_attributes=True)

    space_id: str
    state: str
    confidence: float
    track_id: str | None = None
    score: float | None = None
    is_unknown: bool = False
    is_pending: bool = False


class SourceStatusResponse(BaseModel):
    """Configured camera / model / freshness status."""

    camera_id: str
    source: str
    model_name: str
    model_device: str
    last_frame_at: datetime | None = None
    stale: bool
    max_frame_age_seconds: float
    persistence_enabled: bool


class StatusResponse(BaseModel):
    """Aggregate lot status."""

    camera_id: str
    captured_at: datetime | None
    total_spaces: int
    available: int
    occupied: int
    unknown: int
    occupancy_percent: float
    stale: bool
    source: SourceStatusResponse
    spaces: list[SpaceStatusResponse] = Field(default_factory=list)


class EventResponse(BaseModel):
    """Persisted occupancy event."""

    id: UUID
    run_id: UUID
    space_id: str
    event_type: str
    previous_state: str
    new_state: str
    confirmed_at: datetime
    confidence: float
    track_id: str | None = None
    idempotency_key: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class EventListResponse(BaseModel):
    """Paginated-style event listing."""

    count: int
    events: list[EventResponse]


class HourlyOccupancyResponse(BaseModel):
    """One UTC hour of occupancy event counts."""

    hour_start: datetime
    occupied_events: int
    vacated_events: int
    unknown_events: int


class OccupancyAnalyticsResponse(BaseModel):
    """Hourly occupancy analytics bundle."""

    space_id: str | None = None
    after: datetime | None = None
    before: datetime | None = None
    buckets: list[HourlyOccupancyResponse]
    mean_duration_seconds: float
    completed_stays: int
    still_occupied_stays: int


class TurnoverAnalyticsResponse(BaseModel):
    """Turnover counts for a space or the full lot."""

    space_id: str | None = None
    after: datetime | None = None
    before: datetime | None = None
    occupied_count: int
    vacated_count: int
    unknown_count: int


class RunResponse(BaseModel):
    """Processing run summary."""

    id: str
    camera_id: str
    source_fingerprint: str
    started_at: datetime
    ended_at: datetime | None
    status: str
    model_name: str
    model_version: str | None = None
    frames_read: int
    frames_processed: int
    error_message: str | None = None


class RunListResponse(BaseModel):
    """List of processing runs."""

    count: int
    runs: list[RunResponse]


class ErrorDetail(BaseModel):
    """Structured validation / client error body."""

    detail: str | list[Any]
    error: str = "request_error"

"""Duration, turnover, and hourly occupancy analytics over persisted events."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from smart_parking.domain.events import EventType, OccupancyEvent
from smart_parking.persistence.repository import EventRepository


@dataclass(frozen=True, slots=True)
class ParkingDuration:
    """One occupied stay for a parking space."""

    space_id: str
    run_id: str
    occupied_at: datetime
    vacated_at: datetime | None
    duration_seconds: float
    still_occupied: bool


@dataclass(frozen=True, slots=True)
class TurnoverSummary:
    """Arrival / departure counts for a space or lot over a window."""

    space_id: str | None
    occupied_count: int
    vacated_count: int
    unknown_count: int


@dataclass(frozen=True, slots=True)
class HourlyOccupancyBucket:
    """Aggregate occupancy activity for one UTC hour."""

    hour_start: datetime
    occupied_events: int
    vacated_events: int
    unknown_events: int


def calculate_durations(
    events: list[OccupancyEvent],
    *,
    now: datetime | None = None,
    space_id: str | None = None,
) -> list[ParkingDuration]:
    """Pair OCCUPIED → VACATED transitions; open stays use ``now`` as the end.

    Still-occupied spaces are reported with ``vacated_at=None`` and
    ``still_occupied=True`` so callers can distinguish incomplete stays.
    """
    clock = now if now is not None else datetime.now(UTC)
    if clock.tzinfo is None:
        raise ValueError("now must be timezone-aware (UTC).")

    filtered = [e for e in events if space_id is None or e.space_id == space_id]
    filtered.sort(key=lambda e: (e.space_id, e.confirmed_at))

    open_occupied: dict[str, OccupancyEvent] = {}
    durations: list[ParkingDuration] = []

    for event in filtered:
        if event.event_type == EventType.OCCUPIED:
            open_occupied[event.space_id] = event
        elif event.event_type == EventType.VACATED:
            start = open_occupied.pop(event.space_id, None)
            if start is None:
                continue
            seconds = (event.confirmed_at - start.confirmed_at).total_seconds()
            durations.append(
                ParkingDuration(
                    space_id=event.space_id,
                    run_id=str(start.run_id),
                    occupied_at=start.confirmed_at,
                    vacated_at=event.confirmed_at,
                    duration_seconds=max(0.0, seconds),
                    still_occupied=False,
                )
            )
        elif event.event_type == EventType.UNKNOWN:
            open_occupied.pop(event.space_id, None)

    for space, start in open_occupied.items():
        seconds = (clock - start.confirmed_at).total_seconds()
        durations.append(
            ParkingDuration(
                space_id=space,
                run_id=str(start.run_id),
                occupied_at=start.confirmed_at,
                vacated_at=None,
                duration_seconds=max(0.0, seconds),
                still_occupied=True,
            )
        )

    durations.sort(key=lambda d: d.occupied_at)
    return durations


def calculate_turnover(
    events: list[OccupancyEvent],
    *,
    space_id: str | None = None,
) -> TurnoverSummary:
    """Count occupied / vacated / unknown events (optionally for one space)."""
    filtered = [e for e in events if space_id is None or e.space_id == space_id]
    return TurnoverSummary(
        space_id=space_id,
        occupied_count=sum(1 for e in filtered if e.event_type == EventType.OCCUPIED),
        vacated_count=sum(1 for e in filtered if e.event_type == EventType.VACATED),
        unknown_count=sum(1 for e in filtered if e.event_type == EventType.UNKNOWN),
    )


def hourly_occupancy_summary(
    events: list[OccupancyEvent],
    *,
    space_id: str | None = None,
) -> list[HourlyOccupancyBucket]:
    """Bucket event counts by UTC hour start."""
    filtered = [e for e in events if space_id is None or e.space_id == space_id]
    buckets: dict[datetime, list[int]] = {}
    for event in filtered:
        hour = event.confirmed_at.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
        counts = buckets.setdefault(hour, [0, 0, 0])
        if event.event_type == EventType.OCCUPIED:
            counts[0] += 1
        elif event.event_type == EventType.VACATED:
            counts[1] += 1
        elif event.event_type == EventType.UNKNOWN:
            counts[2] += 1

    return [
        HourlyOccupancyBucket(
            hour_start=hour,
            occupied_events=counts[0],
            vacated_events=counts[1],
            unknown_events=counts[2],
        )
        for hour, counts in sorted(buckets.items(), key=lambda item: item[0])
    ]


def load_and_analyze(
    repository: EventRepository,
    *,
    space_id: str | None = None,
    after: datetime | None = None,
    before: datetime | None = None,
    now: datetime | None = None,
) -> tuple[list[ParkingDuration], TurnoverSummary, list[HourlyOccupancyBucket]]:
    """Fetch events from the repository and compute the standard analytics bundle."""
    events = repository.list_events(space_id=space_id, after=after, before=before)
    return (
        calculate_durations(events, now=now, space_id=space_id),
        calculate_turnover(events, space_id=space_id),
        hourly_occupancy_summary(events, space_id=space_id),
    )


def mean_duration_seconds(
    durations: list[ParkingDuration], *, completed_only: bool = True
) -> float:
    """Average stay length in seconds; optionally exclude still-occupied stays."""
    selected = [d for d in durations if not completed_only or not d.still_occupied]
    if not selected:
        return 0.0
    return sum(d.duration_seconds for d in selected) / len(selected)


def retention_cutoff(*, retention_days: int, now: datetime | None = None) -> datetime:
    """Return the UTC cutoff datetime for retention purges."""
    if retention_days < 1:
        raise ValueError("retention_days must be >= 1.")
    clock = now if now is not None else datetime.now(UTC)
    return clock - timedelta(days=retention_days)

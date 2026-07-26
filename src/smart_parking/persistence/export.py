"""CSV / JSON export helpers for occupancy events."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from smart_parking.domain.events import OccupancyEvent

EVENT_CSV_FIELDS = (
    "id",
    "run_id",
    "space_id",
    "event_type",
    "previous_state",
    "new_state",
    "confirmed_at",
    "raw_transition_started_at",
    "confidence",
    "track_id",
    "idempotency_key",
)


def event_to_row(event: OccupancyEvent) -> dict[str, str]:
    """Flatten an occupancy event for tabular export."""
    return {
        "id": str(event.id),
        "run_id": str(event.run_id),
        "space_id": event.space_id,
        "event_type": event.event_type.value,
        "previous_state": event.previous_state.value,
        "new_state": event.new_state.value,
        "confirmed_at": event.confirmed_at.isoformat(),
        "raw_transition_started_at": (
            event.raw_transition_started_at.isoformat()
            if event.raw_transition_started_at is not None
            else ""
        ),
        "confidence": f"{event.confidence:.6f}",
        "track_id": event.track_id or "",
        "idempotency_key": event.idempotency_key,
    }


def export_events_csv(events: list[OccupancyEvent], output: Path) -> Path:
    """Write occupancy events to a CSV file and return the path."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(EVENT_CSV_FIELDS))
        writer.writeheader()
        for event in events:
            writer.writerow(event_to_row(event))
    return output


def export_events_json(events: list[OccupancyEvent], output: Path) -> Path:
    """Write occupancy events to a JSON array file and return the path."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = [event_to_row(event) for event in events]
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return output

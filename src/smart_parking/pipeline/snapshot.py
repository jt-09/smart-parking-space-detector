"""Occupancy snapshot serialization helpers for pipeline outputs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from smart_parking.domain.state import OccupancySnapshot, SpaceOccupancy


@dataclass(slots=True)
class PipelineMetrics:
    """Timing and throughput counters collected during a processing run."""

    frames_read: int = 0
    frames_processed: int = 0
    frames_skipped: int = 0
    decode_fps: float = 0.0
    inference_fps: float = 0.0
    e2e_fps: float = 0.0
    last_inference_ms: float | None = None
    elapsed_seconds: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _format_utc(moment: datetime) -> str:
    text = moment.isoformat()
    if text.endswith("+00:00"):
        return text[:-6] + "Z"
    return text


def space_occupancy_to_dict(space: SpaceOccupancy) -> dict[str, Any]:
    """Serialize one space occupancy row for JSON output."""
    return {
        "space_id": space.space_id,
        "state": str(space.state),
        "confidence": space.confidence,
        "track_id": space.track_id,
        "score": space.score,
    }


def snapshot_to_dict(
    snapshot: OccupancySnapshot,
    *,
    metrics: PipelineMetrics | None = None,
) -> dict[str, Any]:
    """Convert an occupancy snapshot into a JSON-serializable mapping.

    Uses confirmed (engine) state only — never raw detector scores alone.
    """
    payload: dict[str, Any] = {
        "timestamp": _format_utc(snapshot.captured_at),
        "camera_id": snapshot.camera_id,
        "frame_index": snapshot.frame_index,
        "run_id": snapshot.run_id,
        "available": snapshot.available,
        "occupied": snapshot.occupied,
        "unknown": snapshot.unknown,
        "occupancy_percent": snapshot.occupancy_percent,
        "spaces": [space_occupancy_to_dict(space) for space in snapshot.spaces],
    }
    if metrics is not None:
        payload["metrics"] = {
            "decode_fps": metrics.decode_fps,
            "inference_fps": metrics.inference_fps,
            "e2e_fps": metrics.e2e_fps,
            "last_inference_ms": metrics.last_inference_ms,
            "frames_processed": metrics.frames_processed,
        }
    return payload

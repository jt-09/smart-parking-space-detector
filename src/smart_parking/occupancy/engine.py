"""Occupancy engine: map per-frame evidence onto state machines."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from smart_parking.config.models import GeometrySettings, StateSettings
from smart_parking.domain.parking import ParkingMap
from smart_parking.domain.state import (
    Clock,
    OccupancySnapshot,
    OccupancyState,
    SpaceOccupancy,
    SystemClock,
)
from smart_parking.geometry.assignment import SpaceAssignment
from smart_parking.occupancy.state_machine import (
    DEFAULT_EVIDENCE_HISTORY_MAXLEN,
    OccupancyStateMachine,
)


@dataclass(frozen=True, slots=True)
class SpaceEvidence:
    """Raw occupancy evidence for one space on one frame."""

    space_id: str
    score: float
    track_id: str | None = None


class OccupancyEngine:
    """Maintain temporal occupancy state for every enabled parking space.

    Callers feed assignment scores (or explicit evidence). Unassigned spaces
    receive score ``0.0`` on valid frames. Invalid / source-failure frames
    mark every space invalid so the state machines can move to ``UNKNOWN``.
    """

    def __init__(
        self,
        parking_map: ParkingMap,
        geometry: GeometrySettings | None = None,
        state: StateSettings | None = None,
        clock: Clock | None = None,
        *,
        history_maxlen: int = DEFAULT_EVIDENCE_HISTORY_MAXLEN,
        space_ids: Sequence[str] | None = None,
    ) -> None:
        self._geometry = geometry if geometry is not None else GeometrySettings()
        self._state = state if state is not None else StateSettings()
        self._clock: Clock = clock if clock is not None else SystemClock()
        self._parking_map = parking_map
        self._history_maxlen = history_maxlen

        if space_ids is None:
            ids = [space.id for space in parking_map.enabled_spaces]
        else:
            ids = list(space_ids)
        if not ids:
            raise ValueError("OccupancyEngine requires at least one parking space id.")

        self._machines: dict[str, OccupancyStateMachine] = {
            space_id: OccupancyStateMachine(
                space_id,
                self._geometry,
                self._state,
                self._clock,
                history_maxlen=history_maxlen,
            )
            for space_id in ids
        }

    @property
    def space_ids(self) -> tuple[str, ...]:
        return tuple(self._machines)

    def machine(self, space_id: str) -> OccupancyStateMachine:
        try:
            return self._machines[space_id]
        except KeyError as exc:
            msg = f"Unknown parking space id '{space_id}'."
            raise KeyError(msg) from exc

    def update(
        self,
        evidence: Sequence[SpaceEvidence] | Mapping[str, float],
        *,
        frame_valid: bool = True,
        camera_id: str | None = None,
        frame_index: int | None = None,
        observed_at: datetime | None = None,
        run_id: str | None = None,
    ) -> OccupancySnapshot:
        """Apply per-space scores and return an occupancy snapshot."""
        now = observed_at if observed_at is not None else self._clock.now()
        scores = self._normalize_evidence(evidence)

        spaces: list[SpaceOccupancy] = []
        for space_id, machine in self._machines.items():
            score, track_id = scores.get(space_id, (0.0, None))
            machine.update(
                score,
                frame_valid=frame_valid,
                track_id=track_id,
                observed_at=now,
            )
            spaces.append(
                SpaceOccupancy(
                    space_id=space_id,
                    state=machine.state,
                    confidence=machine.confidence,
                    track_id=machine.track_id,
                    score=machine.last_score,
                )
            )

        return OccupancySnapshot(
            camera_id=camera_id or self._parking_map.camera_id,
            captured_at=now,
            spaces=tuple(spaces),
            frame_index=frame_index,
            run_id=run_id,
        )

    def update_assignments(
        self,
        assignments: Sequence[SpaceAssignment],
        *,
        frame_valid: bool = True,
        camera_id: str | None = None,
        frame_index: int | None = None,
        observed_at: datetime | None = None,
        run_id: str | None = None,
    ) -> OccupancySnapshot:
        """Convenience wrapper that converts geometry assignments to evidence."""
        evidence = [
            SpaceEvidence(
                space_id=item.space_id,
                score=item.score,
                track_id=item.detection.track_id,
            )
            for item in assignments
        ]
        return self.update(
            evidence,
            frame_valid=frame_valid,
            camera_id=camera_id,
            frame_index=frame_index,
            observed_at=observed_at,
            run_id=run_id,
        )

    def states(self) -> dict[str, OccupancyState]:
        return {space_id: machine.state for space_id, machine in self._machines.items()}

    @staticmethod
    def _normalize_evidence(
        evidence: Sequence[SpaceEvidence] | Mapping[str, float],
    ) -> dict[str, tuple[float, str | None]]:
        if isinstance(evidence, Mapping):
            return {space_id: (float(score), None) for space_id, score in evidence.items()}
        result: dict[str, tuple[float, str | None]] = {}
        for item in evidence:
            result[item.space_id] = (float(item.score), item.track_id)
        return result

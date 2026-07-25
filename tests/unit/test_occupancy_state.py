"""Unit tests for temporal occupancy state machine and engine.

Uses synthetic scores and an injectable fake clock — no media, weights, or
detector inference.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from smart_parking.config.models import GeometrySettings, StateSettings
from smart_parking.domain.parking import ParkingMap, ParkingSpace, Point
from smart_parking.domain.state import OccupancyState
from smart_parking.occupancy import (
    DEFAULT_EVIDENCE_HISTORY_MAXLEN,
    OccupancyEngine,
    OccupancyStateMachine,
    SpaceEvidence,
)


@dataclass(slots=True)
class FakeClock:
    """Mutable UTC clock for deterministic time-based confirmation tests."""

    current: datetime

    def now(self) -> datetime:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current = self.current + timedelta(seconds=seconds)


def _geometry(**overrides: float) -> GeometrySettings:
    data = {
        "occupied_enter_threshold": 0.30,
        "occupied_exit_threshold": 0.12,
    }
    data.update(overrides)
    return GeometrySettings(**data)


def _state(**overrides: object) -> StateSettings:
    data: dict[str, object] = {
        "mode": "frames",
        "enter_confirm_frames": 5,
        "exit_confirm_frames": 8,
        "enter_confirm_seconds": 0.5,
        "exit_confirm_seconds": 1.0,
        "unknown_after_invalid_frames": 10,
    }
    data.update(overrides)
    return StateSettings(**data)


def _machine(
    *,
    geometry: GeometrySettings | None = None,
    state: StateSettings | None = None,
    clock: FakeClock | None = None,
    history_maxlen: int = 8,
) -> OccupancyStateMachine:
    return OccupancyStateMachine(
        "A-001",
        geometry or _geometry(),
        state or _state(),
        clock,
        history_maxlen=history_maxlen,
    )


def _parking_map(*space_ids: str) -> ParkingMap:
    spaces = tuple(
        ParkingSpace(
            id=space_id,
            label=space_id,
            polygon=(Point(0, 0), Point(10, 0), Point(10, 10), Point(0, 10)),
        )
        for space_id in space_ids
    )
    return ParkingMap(
        camera_id="lot-a-camera-01",
        reference_width=100,
        reference_height=100,
        spaces=spaces,
    )


def _recover_to_available(machine: OccupancyStateMachine, frames: int = 5) -> None:
    for _ in range(frames):
        machine.update(0.0, frame_valid=True)
    assert machine.state == OccupancyState.AVAILABLE


def _recover_to_occupied(machine: OccupancyStateMachine, frames: int = 5) -> None:
    for _ in range(frames):
        machine.update(0.9, frame_valid=True)
    assert machine.state == OccupancyState.OCCUPIED


def test_starts_unknown() -> None:
    machine = _machine()
    assert machine.state == OccupancyState.UNKNOWN


def test_no_confirmed_transition_on_one_noisy_frame() -> None:
    """Default enter_confirm_frames=5 — one spike must not reach OCCUPIED."""
    machine = _machine()
    _recover_to_available(machine)

    machine.update(0.95, frame_valid=True)
    assert machine.state == OccupancyState.PENDING_OCCUPIED

    machine.update(0.0, frame_valid=True)
    assert machine.state == OccupancyState.AVAILABLE


def test_enter_and_exit_use_different_thresholds() -> None:
    geometry = _geometry(occupied_enter_threshold=0.30, occupied_exit_threshold=0.12)
    machine = _machine(
        geometry=geometry, state=_state(enter_confirm_frames=3, exit_confirm_frames=3)
    )
    _recover_to_available(machine, frames=3)

    # Mid-band score (between exit and enter) must not start pending occupy.
    machine.update(0.20, frame_valid=True)
    assert machine.state == OccupancyState.AVAILABLE

    for _ in range(3):
        machine.update(0.35, frame_valid=True)
    assert machine.state == OccupancyState.OCCUPIED

    # Mid-band while occupied must not start pending vacate.
    machine.update(0.20, frame_valid=True)
    assert machine.state == OccupancyState.OCCUPIED

    for _ in range(3):
        machine.update(0.05, frame_valid=True)
    assert machine.state == OccupancyState.AVAILABLE


def test_pending_enter_cancels_when_evidence_falls() -> None:
    machine = _machine(state=_state(enter_confirm_frames=5))
    _recover_to_available(machine)

    machine.update(0.8, frame_valid=True)
    machine.update(0.8, frame_valid=True)
    assert machine.state == OccupancyState.PENDING_OCCUPIED

    machine.update(0.1, frame_valid=True)
    assert machine.state == OccupancyState.AVAILABLE


def test_pending_exit_cancels_when_evidence_rises() -> None:
    machine = _machine(state=_state(enter_confirm_frames=3, exit_confirm_frames=5))
    _recover_to_occupied(machine, frames=3)

    machine.update(0.05, frame_valid=True)
    machine.update(0.05, frame_valid=True)
    assert machine.state == OccupancyState.PENDING_AVAILABLE

    machine.update(0.5, frame_valid=True)
    assert machine.state == OccupancyState.OCCUPIED


def test_confirmed_enter_after_frame_threshold() -> None:
    machine = _machine(state=_state(enter_confirm_frames=5))
    _recover_to_available(machine)

    for _ in range(4):
        machine.update(0.8, frame_valid=True)
        assert machine.state == OccupancyState.PENDING_OCCUPIED

    machine.update(0.8, frame_valid=True)
    assert machine.state == OccupancyState.OCCUPIED


def test_time_based_enter_confirmation() -> None:
    clock = FakeClock(datetime(2026, 7, 25, 15, 0, tzinfo=UTC))
    machine = _machine(
        state=_state(mode="seconds", enter_confirm_seconds=0.5, exit_confirm_seconds=1.0),
        clock=clock,
    )
    # Recover from UNKNOWN with time-based confirmation.
    machine.update(0.0, frame_valid=True)
    clock.advance(0.5)
    machine.update(0.0, frame_valid=True)
    assert machine.state == OccupancyState.AVAILABLE

    machine.update(0.9, frame_valid=True)
    assert machine.state == OccupancyState.PENDING_OCCUPIED

    clock.advance(0.4)
    machine.update(0.9, frame_valid=True)
    assert machine.state == OccupancyState.PENDING_OCCUPIED

    clock.advance(0.2)
    machine.update(0.9, frame_valid=True)
    assert machine.state == OccupancyState.OCCUPIED


def test_invalid_frames_eventually_produce_unknown() -> None:
    machine = _machine(state=_state(enter_confirm_frames=2, unknown_after_invalid_frames=3))
    _recover_to_available(machine, frames=2)

    machine.update(0.0, frame_valid=False)
    machine.update(0.0, frame_valid=False)
    assert machine.state == OccupancyState.AVAILABLE

    machine.update(0.0, frame_valid=False)
    assert machine.state == OccupancyState.UNKNOWN


def test_occupied_becomes_unknown_after_invalid_streak() -> None:
    machine = _machine(state=_state(enter_confirm_frames=2, unknown_after_invalid_frames=2))
    _recover_to_occupied(machine, frames=2)

    machine.update(0.9, frame_valid=False)
    assert machine.state == OccupancyState.OCCUPIED
    machine.update(0.9, frame_valid=False)
    assert machine.state == OccupancyState.UNKNOWN


def test_recovery_from_unknown_to_available() -> None:
    machine = _machine(state=_state(enter_confirm_frames=3, unknown_after_invalid_frames=2))
    _recover_to_available(machine, frames=3)
    machine.update(0.0, frame_valid=False)
    machine.update(0.0, frame_valid=False)
    assert machine.state == OccupancyState.UNKNOWN

    machine.update(0.0, frame_valid=True)
    machine.update(0.0, frame_valid=True)
    assert machine.state == OccupancyState.UNKNOWN
    machine.update(0.0, frame_valid=True)
    assert machine.state == OccupancyState.AVAILABLE


def test_recovery_from_unknown_to_occupied() -> None:
    machine = _machine(state=_state(enter_confirm_frames=3))
    assert machine.state == OccupancyState.UNKNOWN

    machine.update(0.9, frame_valid=True)
    machine.update(0.9, frame_valid=True)
    assert machine.state == OccupancyState.UNKNOWN
    machine.update(0.9, frame_valid=True)
    assert machine.state == OccupancyState.OCCUPIED


def test_recovery_target_resets_when_evidence_flips() -> None:
    machine = _machine(state=_state(enter_confirm_frames=3))
    machine.update(0.9, frame_valid=True)
    machine.update(0.9, frame_valid=True)
    # Flip to low evidence before confirmation — counter must reset.
    machine.update(0.0, frame_valid=True)
    machine.update(0.0, frame_valid=True)
    assert machine.state == OccupancyState.UNKNOWN
    machine.update(0.0, frame_valid=True)
    assert machine.state == OccupancyState.AVAILABLE


def test_evidence_history_remains_bounded() -> None:
    machine = _machine(history_maxlen=4)
    for i in range(20):
        machine.update(float(i % 5) / 10.0, frame_valid=True)
    assert len(machine.evidence_history) == 4
    assert machine.history_maxlen == 4
    assert len(machine.evidence_history) <= DEFAULT_EVIDENCE_HISTORY_MAXLEN


def test_rejects_naive_timestamp() -> None:
    machine = _machine()
    with pytest.raises(ValueError, match="timezone-aware"):
        machine.update(0.0, observed_at=datetime(2026, 7, 25, 12, 0))


def test_engine_unassigned_spaces_get_zero_evidence() -> None:
    engine = OccupancyEngine(
        _parking_map("A-001", "A-002"),
        geometry=_geometry(),
        state=_state(enter_confirm_frames=2),
        history_maxlen=8,
    )
    # Recover both spaces to AVAILABLE with empty evidence (score 0).
    for _ in range(2):
        snapshot = engine.update([], frame_valid=True)
    assert all(s.state == OccupancyState.AVAILABLE for s in snapshot.spaces)

    snapshot = engine.update(
        [SpaceEvidence("A-001", score=0.9, track_id="t1")],
        frame_valid=True,
    )
    by_id = {s.space_id: s for s in snapshot.spaces}
    assert by_id["A-001"].state == OccupancyState.PENDING_OCCUPIED
    assert by_id["A-001"].track_id == "t1"
    assert by_id["A-002"].state == OccupancyState.AVAILABLE
    assert by_id["A-002"].score == 0.0


def test_engine_mapping_evidence_and_invalid_frame() -> None:
    engine = OccupancyEngine(
        _parking_map("A-001"),
        state=_state(enter_confirm_frames=2, unknown_after_invalid_frames=2),
    )
    for _ in range(2):
        engine.update({"A-001": 0.0}, frame_valid=True)
    assert engine.states()["A-001"] == OccupancyState.AVAILABLE

    engine.update({"A-001": 0.0}, frame_valid=False)
    engine.update({"A-001": 0.0}, frame_valid=False)
    assert engine.states()["A-001"] == OccupancyState.UNKNOWN


def test_engine_requires_space() -> None:
    empty = ParkingMap(
        camera_id="cam",
        reference_width=10,
        reference_height=10,
        spaces=(),
    )
    with pytest.raises(ValueError, match="at least one"):
        OccupancyEngine(empty)


def test_engine_update_assignments_and_machine_lookup() -> None:
    from smart_parking.domain.parking import BoundingBox, Detection
    from smart_parking.geometry.assignment import SpaceAssignment
    from smart_parking.geometry.overlap import OverlapMetrics

    parking = _parking_map("A-001")
    engine = OccupancyEngine(
        parking,
        state=_state(enter_confirm_frames=2),
    )
    assert engine.space_ids == ("A-001",)
    assert engine.machine("A-001").space_id == "A-001"
    with pytest.raises(KeyError, match="Unknown parking space"):
        engine.machine("missing")

    detection = Detection(
        BoundingBox(0, 0, 5, 5),
        confidence=0.9,
        class_id=2,
        class_name="car",
        track_id="trk-9",
    )
    assignment = SpaceAssignment(
        detection_index=0,
        space_id="A-001",
        score=0.9,
        metrics=OverlapMetrics(
            intersection_area=1.0,
            space_overlap=0.5,
            vehicle_overlap=0.5,
            centre_inside=True,
            bottom_centre_inside=True,
            space_area=100.0,
            vehicle_area=25.0,
        ),
        detection=detection,
        space=parking.spaces[0],
    )
    for _ in range(2):
        engine.update({}, frame_valid=True)
    snapshot = engine.update_assignments([assignment], frame_valid=True, frame_index=7)
    assert snapshot.frame_index == 7
    assert snapshot.spaces[0].state == OccupancyState.PENDING_OCCUPIED
    assert snapshot.spaces[0].track_id == "trk-9"


def test_history_maxlen_must_be_positive() -> None:
    with pytest.raises(ValueError, match="history_maxlen"):
        _machine(history_maxlen=0)

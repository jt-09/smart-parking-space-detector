"""Unit tests for domain parking, detection, state, and event models."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from smart_parking.domain import (
    BoundingBox,
    Detection,
    EventType,
    OccupancyEvent,
    OccupancySnapshot,
    OccupancyState,
    ParkingMap,
    ParkingSpace,
    Point,
    SpaceOccupancy,
    SystemClock,
)


def test_bounding_box_geometry() -> None:
    box = BoundingBox(10, 20, 30, 40)
    assert box.width == 20
    assert box.height == 20
    assert box.area == 400
    assert box.center == Point(20, 30)
    assert box.bottom_center == Point(20, 40)
    assert box.as_xyxy() == (10, 20, 30, 40)


def test_bounding_box_rejects_inverted() -> None:
    with pytest.raises(ValueError, match="x2 must be >= x1"):
        BoundingBox(10, 20, 5, 40)


def test_detection_confidence_bounds() -> None:
    Detection(BoundingBox(0, 0, 10, 10), confidence=0.5, class_id=2, class_name="car")
    with pytest.raises(ValueError, match="confidence"):
        Detection(BoundingBox(0, 0, 10, 10), confidence=1.5, class_id=2, class_name="car")


def test_parking_space_requires_triangle() -> None:
    with pytest.raises(ValueError, match="at least 3 points"):
        ParkingSpace(id="A1", label="A1", polygon=(Point(0, 0), Point(1, 0)))


def test_parking_space_area_shoelace() -> None:
    space = ParkingSpace(
        id="A1",
        label="A1",
        polygon=(Point(0, 0), Point(10, 0), Point(10, 5), Point(0, 5)),
    )
    assert space.area == 50.0


def test_parking_map_rejects_duplicate_ids() -> None:
    space = ParkingSpace(
        id="A1",
        label="A1",
        polygon=(Point(0, 0), Point(10, 0), Point(10, 10)),
    )
    with pytest.raises(ValueError, match="Duplicate parking space id"):
        ParkingMap(
            camera_id="cam",
            reference_width=100,
            reference_height=100,
            spaces=(space, space),
        )


def test_system_clock_is_utc() -> None:
    now = SystemClock().now()
    assert now.tzinfo is not None
    assert now.utcoffset() is not None
    assert now.utcoffset().total_seconds() == 0


def test_occupancy_snapshot_counts() -> None:
    snapshot = OccupancySnapshot(
        camera_id="cam",
        captured_at=datetime(2026, 7, 23, 12, 0, tzinfo=UTC),
        spaces=(
            SpaceOccupancy("A1", OccupancyState.AVAILABLE, confidence=0.9),
            SpaceOccupancy("A2", OccupancyState.OCCUPIED, confidence=0.8),
            SpaceOccupancy("A3", OccupancyState.UNKNOWN, confidence=0.1),
            SpaceOccupancy("A4", OccupancyState.PENDING_OCCUPIED, confidence=0.4),
        ),
    )
    assert snapshot.available == 1
    assert snapshot.occupied == 1
    assert snapshot.unknown == 2
    assert snapshot.occupancy_percent == 50.0


def test_occupancy_event_requires_aware_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        OccupancyEvent(
            id=uuid4(),
            run_id=uuid4(),
            space_id="A1",
            event_type=EventType.OCCUPIED,
            previous_state=OccupancyState.AVAILABLE,
            new_state=OccupancyState.OCCUPIED,
            confirmed_at=datetime(2026, 7, 23, 12, 0),
            confidence=0.9,
            idempotency_key="run:A1:occupied:1",
        )


def test_occupancy_event_valid_and_guards() -> None:
    event = OccupancyEvent(
        id=uuid4(),
        run_id=uuid4(),
        space_id="A1",
        event_type=EventType.VACATED,
        previous_state=OccupancyState.OCCUPIED,
        new_state=OccupancyState.AVAILABLE,
        confirmed_at=datetime(2026, 7, 23, 12, 0, tzinfo=UTC),
        confidence=0.95,
        idempotency_key="run:A1:vacated:1",
        raw_transition_started_at=datetime(2026, 7, 23, 11, 59, tzinfo=UTC),
    )
    assert event.event_type is EventType.VACATED

    with pytest.raises(ValueError, match="raw_transition_started_at"):
        OccupancyEvent(
            id=uuid4(),
            run_id=uuid4(),
            space_id="A1",
            event_type=EventType.OCCUPIED,
            previous_state=OccupancyState.AVAILABLE,
            new_state=OccupancyState.OCCUPIED,
            confirmed_at=datetime(2026, 7, 23, 12, 0, tzinfo=UTC),
            confidence=0.9,
            idempotency_key="k",
            raw_transition_started_at=datetime(2026, 7, 23, 11, 59),
        )
    with pytest.raises(ValueError, match="confidence"):
        OccupancyEvent(
            id=uuid4(),
            run_id=uuid4(),
            space_id="A1",
            event_type=EventType.OCCUPIED,
            previous_state=OccupancyState.AVAILABLE,
            new_state=OccupancyState.OCCUPIED,
            confirmed_at=datetime(2026, 7, 23, 12, 0, tzinfo=UTC),
            confidence=1.2,
            idempotency_key="k",
        )
    with pytest.raises(ValueError, match="idempotency_key"):
        OccupancyEvent(
            id=uuid4(),
            run_id=uuid4(),
            space_id="A1",
            event_type=EventType.OCCUPIED,
            previous_state=OccupancyState.AVAILABLE,
            new_state=OccupancyState.OCCUPIED,
            confirmed_at=datetime(2026, 7, 23, 12, 0, tzinfo=UTC),
            confidence=0.5,
            idempotency_key="  ",
        )
    with pytest.raises(ValueError, match="space_id"):
        OccupancyEvent(
            id=uuid4(),
            run_id=uuid4(),
            space_id=" ",
            event_type=EventType.OCCUPIED,
            previous_state=OccupancyState.AVAILABLE,
            new_state=OccupancyState.OCCUPIED,
            confirmed_at=datetime(2026, 7, 23, 12, 0, tzinfo=UTC),
            confidence=0.5,
            idempotency_key="k",
        )


def test_parking_map_get_and_validation() -> None:
    space = ParkingSpace(
        id="A1",
        label="A1",
        polygon=(Point(0, 0), Point(10, 0), Point(10, 10)),
    )
    parking_map = ParkingMap(
        camera_id="cam",
        reference_width=100,
        reference_height=100,
        spaces=(space,),
    )
    assert parking_map.get("A1").id == "A1"
    with pytest.raises(KeyError, match="Unknown parking space"):
        parking_map.get("missing")
    with pytest.raises(ValueError, match="positive"):
        ParkingMap(camera_id="cam", reference_width=0, reference_height=100, spaces=())
    with pytest.raises(ValueError, match="camera_id"):
        ParkingMap(camera_id=" ", reference_width=10, reference_height=10, spaces=())
    with pytest.raises(ValueError, match="non-empty"):
        ParkingSpace(id=" ", label="x", polygon=(Point(0, 0), Point(1, 0), Point(0, 1)))
    assert Point(1, 2).as_tuple() == (1.0, 2.0)


def test_space_occupancy_and_empty_snapshot() -> None:
    with pytest.raises(ValueError, match="confidence"):
        SpaceOccupancy("A1", OccupancyState.AVAILABLE, confidence=2.0)
    with pytest.raises(ValueError, match="timezone-aware"):
        OccupancySnapshot(
            camera_id="cam",
            captured_at=datetime(2026, 7, 23, 12, 0),
            spaces=(),
        )
    empty = OccupancySnapshot(
        camera_id="cam",
        captured_at=datetime(2026, 7, 23, 12, 0, tzinfo=UTC),
        spaces=(),
    )
    assert empty.occupancy_percent == 0.0

"""Unit tests for geometry overlap metrics and deterministic assignment."""

from __future__ import annotations

import pytest
from shapely.geometry import Polygon

from smart_parking.config.models import GeometrySettings
from smart_parking.domain.parking import (
    BoundingBox,
    Detection,
    ParkingMap,
    ParkingSpace,
    Point,
)
from smart_parking.geometry import (
    GeometryError,
    assign_detections,
    assign_greedy,
    bbox_to_polygon,
    build_candidates,
    compute_overlap,
    compute_overlap_polygons,
    detection_footprint,
    map_for_frame,
    parking_space_to_polygon,
    points_to_polygon,
    score_detection_space,
    weighted_occupancy_score,
)


def _rect_space(
    space_id: str,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    *,
    enabled: bool = True,
) -> ParkingSpace:
    return ParkingSpace(
        id=space_id,
        label=space_id,
        enabled=enabled,
        polygon=(
            Point(x0, y0),
            Point(x1, y0),
            Point(x1, y1),
            Point(x0, y1),
        ),
    )


def _detection(x1: float, y1: float, x2: float, y2: float, *, conf: float = 0.9) -> Detection:
    return Detection(
        bbox=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2),
        confidence=conf,
        class_id=2,
        class_name="car",
    )


def make_settings(**overrides: object) -> GeometrySettings:
    payload: dict[str, object] = {
        "footprint_height_ratio": 1.0,
        "candidate_score_threshold": 0.18,
        "weight_space_overlap": 0.55,
        "weight_vehicle_overlap": 0.20,
        "weight_center_inside": 0.10,
        "weight_bottom_center_inside": 0.15,
    }
    payload.update(overrides)
    return GeometrySettings.model_validate(payload)


def test_points_to_polygon_rejects_too_few_vertices() -> None:
    with pytest.raises(GeometryError, match="at least 3 polygon vertices"):
        points_to_polygon((Point(0.0, 0.0), Point(1.0, 1.0)), context="tiny")


def test_bbox_rejects_zero_area() -> None:
    bbox = BoundingBox(x1=5.0, y1=5.0, x2=5.0, y2=10.0)
    with pytest.raises(GeometryError, match="non-positive area"):
        bbox_to_polygon(bbox, footprint_height_ratio=1.0)


def test_points_to_polygon_exact_area() -> None:
    polygon = points_to_polygon(
        (Point(0.0, 0.0), Point(10.0, 0.0), Point(10.0, 5.0), Point(0.0, 5.0)),
        context="test rect",
    )
    assert polygon.area == pytest.approx(50.0)


def test_bbox_footprint_height_ratio_lower_portion() -> None:
    bbox = BoundingBox(x1=0.0, y1=0.0, x2=10.0, y2=100.0)
    footprint = bbox_to_polygon(bbox, footprint_height_ratio=0.60)
    # Lower 60% => top at y=40, height 60, width 10 => area 600
    assert footprint.area == pytest.approx(600.0)
    assert footprint.bounds == pytest.approx((0.0, 40.0, 10.0, 100.0))


def test_detection_footprint_matches_bbox_helper() -> None:
    bbox = BoundingBox(x1=1.0, y1=2.0, x2=11.0, y2=22.0)
    assert detection_footprint(bbox, footprint_height_ratio=0.5).equals(
        bbox_to_polygon(bbox, footprint_height_ratio=0.5)
    )


def test_compute_overlap_exact_full_containment() -> None:
    space = _rect_space("A-001", 0.0, 0.0, 100.0, 100.0)
    detection = _detection(10.0, 10.0, 40.0, 40.0)
    metrics = compute_overlap(detection, space, footprint_height_ratio=1.0)

    assert metrics.intersection_area == pytest.approx(900.0)
    assert metrics.space_area == pytest.approx(10_000.0)
    assert metrics.vehicle_area == pytest.approx(900.0)
    assert metrics.space_overlap == pytest.approx(0.09)
    assert metrics.vehicle_overlap == pytest.approx(1.0)
    assert metrics.centre_inside is True
    assert metrics.bottom_centre_inside is True


def test_compute_overlap_partial_intersection() -> None:
    space = _rect_space("B-001", 0.0, 0.0, 10.0, 10.0)
    # Box overlaps left half of space: intersection 5x10 = 50
    detection = _detection(-5.0, 0.0, 5.0, 10.0)
    metrics = compute_overlap(detection, space, footprint_height_ratio=1.0)

    assert metrics.intersection_area == pytest.approx(50.0)
    assert metrics.space_overlap == pytest.approx(0.5)
    assert metrics.vehicle_overlap == pytest.approx(0.5)
    # Centre of box at (0, 5) — on the left edge of the space; covers => inside
    assert metrics.centre_inside is True
    assert metrics.bottom_centre_inside is True


def test_compute_overlap_polygons_centre_outside() -> None:
    vehicle = Polygon([(0.0, 0.0), (20.0, 0.0), (20.0, 10.0), (0.0, 10.0)])
    space = Polygon([(50.0, 50.0), (60.0, 50.0), (60.0, 60.0), (50.0, 60.0)])
    metrics = compute_overlap_polygons(
        vehicle,
        space,
        centre=Point(10.0, 5.0),
        bottom_centre=Point(10.0, 10.0),
    )
    assert metrics.intersection_area == pytest.approx(0.0)
    assert metrics.space_overlap == pytest.approx(0.0)
    assert metrics.vehicle_overlap == pytest.approx(0.0)
    assert metrics.centre_inside is False
    assert metrics.bottom_centre_inside is False


def test_weighted_occupancy_score_exact_formula() -> None:
    space = _rect_space("A-001", 0.0, 0.0, 100.0, 100.0)
    detection = _detection(10.0, 10.0, 40.0, 40.0)
    settings = make_settings()
    metrics = compute_overlap(detection, space, footprint_height_ratio=1.0)

    expected = (
        0.55 * metrics.space_overlap + 0.20 * metrics.vehicle_overlap + 0.10 * 1.0 + 0.15 * 1.0
    )
    assert weighted_occupancy_score(metrics, settings) == pytest.approx(expected)
    # 0.55*0.09 + 0.20*1.0 + 0.10 + 0.15 = 0.0495 + 0.20 + 0.25 = 0.4995
    assert expected == pytest.approx(0.4995)


def test_invalid_self_intersecting_polygon_actionable_error() -> None:
    # Bow-tie
    with pytest.raises(GeometryError, match="not a valid polygon|Redraw"):
        points_to_polygon(
            (Point(0.0, 0.0), Point(10.0, 10.0), Point(0.0, 10.0), Point(10.0, 0.0)),
            context="Parking space 'X'",
        )


def test_parking_space_to_polygon_rejects_collinear() -> None:
    space = ParkingSpace(
        id="flat",
        label="flat",
        polygon=(Point(0.0, 0.0), Point(10.0, 0.0), Point(20.0, 0.0)),
    )
    with pytest.raises(GeometryError, match="non-positive area|Redraw"):
        parking_space_to_polygon(space)


def test_invalid_footprint_ratio() -> None:
    bbox = BoundingBox(x1=0.0, y1=0.0, x2=10.0, y2=10.0)
    with pytest.raises(GeometryError, match="footprint_height_ratio"):
        bbox_to_polygon(bbox, footprint_height_ratio=0.0)


def test_single_vehicle_cannot_occupy_multiple_spaces() -> None:
    parking_map = ParkingMap(
        camera_id="cam",
        reference_width=200,
        reference_height=100,
        spaces=(
            _rect_space("A-001", 0.0, 0.0, 50.0, 50.0),
            _rect_space("A-002", 40.0, 0.0, 90.0, 50.0),
        ),
    )
    # Wide vehicle overlapping both spaces strongly
    detections = (_detection(5.0, 5.0, 85.0, 45.0),)
    assignments = assign_detections(detections, parking_map, make_settings())

    assert len(assignments) == 1
    assigned_spaces = {a.space_id for a in assignments}
    assert len(assigned_spaces) == 1
    detection_indices = {a.detection_index for a in assignments}
    assert detection_indices == {0}


def test_assignment_tie_deterministic_by_space_id() -> None:
    """Equal scores: prefer lexicographically smaller space id."""
    from smart_parking.geometry.assignment import ScoredCandidate
    from smart_parking.geometry.overlap import OverlapMetrics

    zero = OverlapMetrics(
        intersection_area=0.0,
        space_overlap=0.0,
        vehicle_overlap=0.0,
        centre_inside=False,
        bottom_centre_inside=False,
        space_area=1.0,
        vehicle_area=1.0,
    )
    # One detection, two equal-score spaces — A-001 wins over B-002
    chosen = assign_greedy(
        [
            ScoredCandidate(0, "B-002", 0.5, zero),
            ScoredCandidate(0, "A-001", 0.5, zero),
        ]
    )
    assert len(chosen) == 1
    assert chosen[0].space_id == "A-001"

    # Two detections, equal scores across complementary spaces
    chosen_two = assign_greedy(
        [
            ScoredCandidate(0, "B-002", 0.5, zero),
            ScoredCandidate(0, "A-001", 0.5, zero),
            ScoredCandidate(1, "B-002", 0.5, zero),
        ]
    )
    by_det = {c.detection_index: c.space_id for c in chosen_two}
    assert by_det[0] == "A-001"
    assert by_det[1] == "B-002"


def test_assignment_tie_detection_index_when_same_space_contention() -> None:
    from smart_parking.geometry.assignment import ScoredCandidate
    from smart_parking.geometry.overlap import OverlapMetrics

    zero = OverlapMetrics(
        intersection_area=0.0,
        space_overlap=0.0,
        vehicle_overlap=0.0,
        centre_inside=False,
        bottom_centre_inside=False,
        space_area=1.0,
        vehicle_area=1.0,
    )
    # Same space, equal score, two detections — lower detection index wins
    chosen = assign_greedy(
        [
            ScoredCandidate(3, "A-001", 0.4, zero),
            ScoredCandidate(1, "A-001", 0.4, zero),
        ]
    )
    assert len(chosen) == 1
    assert chosen[0].detection_index == 1


def test_candidate_threshold_filters_weak_pairs() -> None:
    parking_map = ParkingMap(
        camera_id="cam",
        reference_width=100,
        reference_height=100,
        spaces=(_rect_space("A-001", 0.0, 0.0, 50.0, 50.0),),
    )
    # Tiny corner overlap should score below a high threshold
    detections = (_detection(48.0, 48.0, 60.0, 60.0),)
    settings = make_settings(candidate_score_threshold=0.95)
    assert build_candidates(detections, parking_map, settings) == []


def test_disabled_spaces_are_ignored() -> None:
    parking_map = ParkingMap(
        camera_id="cam",
        reference_width=100,
        reference_height=100,
        spaces=(
            _rect_space("A-001", 0.0, 0.0, 50.0, 50.0, enabled=False),
            _rect_space("A-002", 50.0, 0.0, 100.0, 50.0, enabled=True),
        ),
    )
    detections = (_detection(5.0, 5.0, 45.0, 45.0),)
    assignments = assign_detections(detections, parking_map, make_settings())
    assert assignments == []


def test_coordinate_scaling_when_frame_differs_from_map() -> None:
    parking_map = ParkingMap(
        camera_id="cam",
        reference_width=100,
        reference_height=50,
        spaces=(_rect_space("A-001", 10.0, 10.0, 30.0, 30.0),),
    )
    # Frame is 2x resolution; detection already in frame coords covering scaled space
    detections = (_detection(20.0, 20.0, 60.0, 60.0),)
    assignments = assign_detections(
        detections,
        parking_map,
        make_settings(),
        frame_width=200,
        frame_height=100,
    )
    assert len(assignments) == 1
    assert assignments[0].space_id == "A-001"
    # Scaled space is [20,20]-[60,60] => area 1600; full containment
    assert assignments[0].metrics.vehicle_overlap == pytest.approx(1.0)
    assert assignments[0].metrics.space_overlap == pytest.approx(1.0)


def test_map_for_frame_noop_without_dimensions() -> None:
    parking_map = ParkingMap(
        camera_id="cam",
        reference_width=100,
        reference_height=50,
        spaces=(_rect_space("A-001", 10.0, 10.0, 30.0, 30.0),),
    )
    assert map_for_frame(parking_map, frame_width=None, frame_height=None) is parking_map


def test_score_detection_space_includes_index() -> None:
    space = _rect_space("Z-9", 0.0, 0.0, 20.0, 20.0)
    detection = _detection(0.0, 0.0, 20.0, 20.0)
    candidate = score_detection_space(detection, space, make_settings(), detection_index=4)
    assert candidate.detection_index == 4
    assert candidate.space_id == "Z-9"
    assert candidate.score == pytest.approx(1.0)

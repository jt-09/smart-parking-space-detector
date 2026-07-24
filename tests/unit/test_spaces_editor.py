"""Tests for parking-map serialization, scaling, validation, and editor core."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from smart_parking.config import ConfigError, load_parking_map
from smart_parking.domain.parking import ParkingMap, ParkingSpace, Point
from smart_parking.spaces import (
    PolygonValidationError,
    is_self_intersecting,
    parking_map_to_dict,
    save_parking_map,
    scale_parking_map,
    validate_parking_map,
)
from smart_parking.tools import polygon_editor as editor_mod
from smart_parking.tools.polygon_editor import (
    ParkingMapEditor,
    build_editor_for_frame,
    display_available,
    handle_editor_click,
    handle_editor_key,
    run_polygon_editor,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_MAP = REPO_ROOT / "configs" / "parking_spaces.example.json"


def _rect(space_id: str, x0: float, y0: float, x1: float, y1: float) -> ParkingSpace:
    return ParkingSpace(
        id=space_id,
        label=space_id,
        polygon=(
            Point(x0, y0),
            Point(x1, y0),
            Point(x1, y1),
            Point(x0, y1),
        ),
    )


def test_example_map_round_trip(tmp_path: Path) -> None:
    original = load_parking_map(EXAMPLE_MAP)
    out = tmp_path / "roundtrip.json"
    save_parking_map(original, out)
    reloaded = load_parking_map(out)
    assert parking_map_to_dict(reloaded) == parking_map_to_dict(original)


def test_scale_parking_map_doubles_coordinates() -> None:
    parking_map = ParkingMap(
        camera_id="cam",
        reference_width=100,
        reference_height=50,
        spaces=(_rect("A1", 10, 10, 30, 30),),
    )
    scaled = scale_parking_map(parking_map, target_width=200, target_height=100)
    assert scaled.reference_width == 200
    assert scaled.reference_height == 100
    space = scaled.get("A1")
    assert space.polygon[0] == Point(20.0, 20.0)
    assert space.polygon[2] == Point(60.0, 60.0)


def test_scale_same_resolution_is_noop() -> None:
    parking_map = load_parking_map(EXAMPLE_MAP)
    scaled = scale_parking_map(
        parking_map,
        target_width=parking_map.reference_width,
        target_height=parking_map.reference_height,
    )
    assert scaled is parking_map


def test_scale_rejects_non_positive_targets() -> None:
    parking_map = load_parking_map(EXAMPLE_MAP)
    with pytest.raises(ValueError, match="positive"):
        scale_parking_map(parking_map, target_width=0, target_height=100)


def test_self_intersecting_bowtie_detected() -> None:
    bowtie = (
        Point(0, 0),
        Point(10, 10),
        Point(10, 0),
        Point(0, 10),
    )
    assert is_self_intersecting(bowtie) is True


def test_simple_rectangle_not_self_intersecting() -> None:
    rect = (
        Point(0, 0),
        Point(10, 0),
        Point(10, 10),
        Point(0, 10),
    )
    assert is_self_intersecting(rect) is False


def test_triangle_never_self_intersecting() -> None:
    assert is_self_intersecting((Point(0, 0), Point(10, 0), Point(5, 8))) is False


def test_collinear_interior_overlap_detected() -> None:
    from smart_parking.spaces.validation import segments_properly_intersect

    assert (
        segments_properly_intersect(
            Point(0, 0),
            Point(10, 0),
            Point(2, 0),
            Point(8, 0),
        )
        is True
    )


def test_validate_rejects_self_crossing_space() -> None:
    parking_map = ParkingMap(
        camera_id="cam",
        reference_width=100,
        reference_height=100,
        spaces=(
            ParkingSpace(
                id="X1",
                label="X1",
                polygon=(
                    Point(0, 0),
                    Point(50, 50),
                    Point(50, 0),
                    Point(0, 50),
                ),
            ),
        ),
    )
    with pytest.raises(PolygonValidationError, match="self-intersecting"):
        validate_parking_map(parking_map)


def test_load_rejects_self_crossing_json(tmp_path: Path) -> None:
    path = tmp_path / "bowtie.json"
    path.write_text(
        json.dumps(
            {
                "camera_id": "cam",
                "reference_width": 100,
                "reference_height": 100,
                "spaces": [
                    {
                        "id": "X1",
                        "label": "X1",
                        "polygon": [[0, 0], [50, 50], [50, 0], [0, 50]],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="self-intersecting"):
        load_parking_map(path)


def test_save_rejects_invalid_map(tmp_path: Path) -> None:
    parking_map = ParkingMap(
        camera_id="cam",
        reference_width=100,
        reference_height=100,
        spaces=(
            ParkingSpace(
                id="X1",
                label="X1",
                polygon=(
                    Point(0, 0),
                    Point(50, 50),
                    Point(50, 0),
                    Point(0, 50),
                ),
            ),
        ),
    )
    with pytest.raises(PolygonValidationError, match="self-intersecting"):
        save_parking_map(parking_map, tmp_path / "bad.json")


def test_editor_add_undo_and_serialize(tmp_path: Path) -> None:
    editor = ParkingMapEditor.create_empty(
        camera_id="lot-a",
        reference_width=200,
        reference_height=100,
    )
    editor.start_space("A1", "Space A1", zone="A")
    editor.add_point(10, 10)
    editor.add_point(40, 10)
    editor.add_point(40, 40)
    editor.undo_point()
    assert len(editor.active_space.points) == 2  # type: ignore[union-attr]
    editor.add_point(40, 40)
    editor.add_point(10, 40)

    out = tmp_path / "edited.json"
    editor.save(out)
    reloaded = load_parking_map(out)
    assert reloaded.camera_id == "lot-a"
    assert reloaded.get("A1").label == "Space A1"
    assert len(reloaded.get("A1").polygon) == 4


def test_editor_delete_and_disable() -> None:
    editor = ParkingMapEditor.create_empty(
        camera_id="cam",
        reference_width=100,
        reference_height=100,
    )
    editor.start_space("A1")
    for x, y in ((0, 0), (20, 0), (20, 20), (0, 20)):
        editor.add_point(x, y)
    editor.start_space("A2")
    for x, y in ((30, 0), (50, 0), (50, 20), (30, 20)):
        editor.add_point(x, y)
    editor.select_space_by_id("A1")
    editor.set_active_enabled(False)
    editor.select_space_by_id("A2")
    editor.delete_active_space()
    parking_map = editor.to_parking_map()
    assert [s.id for s in parking_map.spaces] == ["A1"]
    assert parking_map.get("A1").enabled is False


def test_editor_rejects_incomplete_save() -> None:
    editor = ParkingMapEditor.create_empty(
        camera_id="cam",
        reference_width=100,
        reference_height=100,
    )
    editor.start_space("A1")
    editor.add_point(0, 0)
    editor.add_point(10, 0)
    with pytest.raises(PolygonValidationError, match="at least 3 points"):
        editor.to_parking_map()


def test_editor_scale_to() -> None:
    editor = ParkingMapEditor.create_empty(
        camera_id="cam",
        reference_width=100,
        reference_height=100,
    )
    editor.start_space("A1")
    for x, y in ((10, 10), (30, 10), (30, 30), (10, 30)):
        editor.add_point(x, y)
    scaled_editor = editor.scale_to(target_width=200, target_height=200)
    assert scaled_editor.reference_width == 200
    assert scaled_editor.spaces[0].points[0] == Point(20.0, 20.0)


def test_editor_point_out_of_bounds() -> None:
    editor = ParkingMapEditor.create_empty(
        camera_id="cam",
        reference_width=50,
        reference_height=50,
    )
    editor.start_space("A1")
    with pytest.raises(ValueError, match="outside reference width"):
        editor.add_point(60, 10)
    with pytest.raises(ValueError, match="outside reference height"):
        editor.add_point(10, 60)


def test_editor_rename_and_duplicate_guards() -> None:
    editor = ParkingMapEditor.create_empty(
        camera_id="cam",
        reference_width=100,
        reference_height=100,
    )
    editor.start_space("A1")
    for x, y in ((0, 0), (10, 0), (10, 10), (0, 10)):
        editor.add_point(x, y)
    editor.start_space("A2")
    for x, y in ((20, 0), (30, 0), (30, 10), (20, 10)):
        editor.add_point(x, y)
    editor.select_space_by_id("A2")
    with pytest.raises(ValueError, match="Duplicate"):
        editor.rename_active(space_id="A1")
    editor.rename_active(space_id="B2", label="Bay B2")
    assert editor.active_space is not None
    assert editor.active_space.id == "B2"
    assert editor.active_space.label == "Bay B2"
    with pytest.raises(ValueError, match="non-empty"):
        editor.start_space("  ")
    with pytest.raises(ValueError, match="Duplicate"):
        editor.start_space("A1")


def test_editor_from_map_and_select_errors() -> None:
    parking_map = load_parking_map(EXAMPLE_MAP)
    editor = ParkingMapEditor.from_parking_map(parking_map)
    assert editor.active_index == 0
    with pytest.raises(IndexError):
        editor.select_space(99)
    with pytest.raises(KeyError):
        editor.select_space_by_id("missing")
    with pytest.raises(RuntimeError, match="No active space"):
        empty = ParkingMapEditor.create_empty(
            camera_id="cam",
            reference_width=10,
            reference_height=10,
        )
        empty.add_point(1, 1)


def test_handle_click_and_keys(tmp_path: Path) -> None:
    editor = ParkingMapEditor.create_empty(
        camera_id="cam",
        reference_width=100,
        reference_height=100,
    )
    handle_editor_click(editor, 10, 10)
    assert editor.active_space is not None
    assert editor.active_space.id == "S1"
    handle_editor_click(editor, 40, 10)
    handle_editor_click(editor, 40, 40)
    handle_editor_click(editor, 10, 40)

    out = tmp_path / "from_keys.json"
    quit_flag, saved = handle_editor_key(editor, ord("s"), output_path=out)
    assert quit_flag is False
    assert saved == out
    assert load_parking_map(out).get("S1").area > 0

    handle_editor_key(editor, ord("n"), output_path=out)
    assert editor.spaces[-1].id == "S2"
    handle_editor_key(editor, ord("["), output_path=out)
    handle_editor_key(editor, ord("]"), output_path=out)
    handle_editor_key(editor, ord("e"), output_path=out)
    handle_editor_key(editor, ord("u"), output_path=out)
    quit_flag, _ = handle_editor_key(editor, ord("q"), output_path=out)
    assert quit_flag is True

    editor.select_space_by_id("S2")
    _, failed = handle_editor_key(editor, ord("s"), output_path=tmp_path / "bad.json")
    assert failed is None
    assert "Save failed" in editor.status_message


def test_build_editor_scales_existing() -> None:
    frame = np.zeros((100, 200, 3), dtype=np.uint8)
    editor = build_editor_for_frame(
        frame,
        camera_id="override",
        existing_map=EXAMPLE_MAP,
        scale_to_source=True,
    )
    assert editor.reference_width == 200
    assert editor.reference_height == 100
    expected_x = 100 * (200 / 1280)
    expected_y = 200 * (100 / 720)
    assert editor.spaces[0].points[0] == Point(expected_x, expected_y)

    empty = build_editor_for_frame(frame, camera_id="fresh")
    assert empty.camera_id == "fresh"
    assert empty.spaces == []


def test_extract_frame_and_overlay(tmp_path: Path) -> None:
    image_path = tmp_path / "ref.png"
    video_path = tmp_path / "ref.avi"
    frame = np.zeros((60, 80, 3), dtype=np.uint8)
    frame[:] = (30, 60, 90)
    assert cv2.imwrite(str(image_path), frame)

    loaded = editor_mod._extract_first_frame(image_path)
    assert loaded.shape == (60, 80, 3)

    fourcc = cv2.VideoWriter_fourcc(*"MJPG")
    writer = cv2.VideoWriter(str(video_path), fourcc, 5.0, (80, 60))
    assert writer.isOpened()
    writer.write(frame)
    writer.write(frame)
    writer.release()

    video_frame = editor_mod._extract_first_frame(video_path)
    assert video_frame.shape[0] == 60
    assert video_frame.shape[1] == 80

    editor = ParkingMapEditor.create_empty(
        camera_id="cam",
        reference_width=80,
        reference_height=60,
    )
    editor.start_space("A1")
    for x, y in ((5, 5), (40, 5), (40, 40), (5, 40)):
        editor.add_point(x, y)
    editor.set_active_enabled(False)
    overlay = editor_mod._draw_overlay(loaded, editor)
    assert overlay.shape == loaded.shape

    with pytest.raises(FileNotFoundError):
        editor_mod._load_reference_image(tmp_path / "missing.png")


def test_display_available_respects_force_headless(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMART_PARKING_FORCE_HEADLESS", "1")
    assert display_available() is False
    monkeypatch.delenv("SMART_PARKING_FORCE_HEADLESS", raising=False)
    monkeypatch.setenv("CI", "true")
    assert display_available() is False


def test_run_polygon_editor_requires_display(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SMART_PARKING_FORCE_HEADLESS", "1")
    image = tmp_path / "ref.png"
    cv2.imwrite(str(image), np.zeros((20, 20, 3), dtype=np.uint8))
    with pytest.raises(RuntimeError, match="No interactive display"):
        run_polygon_editor(source=image, output=tmp_path / "out.json")


@pytest.mark.skipif(not display_available(), reason="No interactive display for GUI smoke")
def test_gui_smoke_optional() -> None:
    """Optional GUI smoke — skipped in CI / headless environments."""
    assert display_available() is True

"""Unit tests for layered configuration and parking-map validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from smart_parking.config import ConfigError, load_parking_map, load_settings

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_CONFIG = REPO_ROOT / "configs" / "app.example.yaml"
EXAMPLE_MAP = REPO_ROOT / "configs" / "parking_spaces.example.json"


def test_example_config_loads() -> None:
    settings = load_settings(EXAMPLE_CONFIG)
    assert settings.camera.id == "lot-a-camera-01"
    assert settings.model.confidence == 0.30
    assert settings.geometry.parking_map == Path("configs/parking_spaces.example.json")
    assert settings.api.port == 8000


def test_example_parking_map_loads() -> None:
    parking_map = load_parking_map(EXAMPLE_MAP)
    assert parking_map.camera_id == "lot-a-camera-01"
    assert len(parking_map.spaces) == 3
    assert parking_map.get("A1").area > 0
    assert {space.id for space in parking_map.enabled_spaces} == {"A1", "A2", "B1"}


def test_defaults_without_yaml() -> None:
    settings = load_settings()
    assert settings.app.environment == "development"
    assert settings.model.name == "yolo26n.pt"


def test_yaml_overrides_defaults(tmp_path: Path) -> None:
    config = tmp_path / "app.yaml"
    config.write_text("camera:\n  id: yaml-cam\n  source: data/custom.mp4\n", encoding="utf-8")
    settings = load_settings(config)
    assert settings.camera.id == "yaml-cam"
    assert settings.camera.source == "data/custom.mp4"
    assert settings.app.log_level == "INFO"


def test_env_overrides_yaml(tmp_path: Path) -> None:
    config = tmp_path / "app.yaml"
    config.write_text("app:\n  log_level: WARNING\ncamera:\n  id: yaml-cam\n", encoding="utf-8")
    settings = load_settings(
        config,
        environ={
            "SMART_PARKING_LOG_LEVEL": "ERROR",
            "SMART_PARKING_CAMERA_ID": "env-cam",
            "SMART_PARKING_DATABASE_URL": "sqlite:///tmp/env.db",
        },
    )
    assert settings.app.log_level == "ERROR"
    assert settings.camera.id == "env-cam"
    assert settings.persistence.database_url == "sqlite:///tmp/env.db"


def test_nested_env_double_underscore(tmp_path: Path) -> None:
    config = tmp_path / "app.yaml"
    config.write_text("model:\n  confidence: 0.2\n", encoding="utf-8")
    settings = load_settings(
        config,
        environ={"SMART_PARKING_MODEL__CONFIDENCE": "0.55"},
    )
    assert settings.model.confidence == 0.55


def test_overrides_beat_env(tmp_path: Path) -> None:
    config = tmp_path / "app.yaml"
    config.write_text("api:\n  port: 8000\n", encoding="utf-8")
    settings = load_settings(
        config,
        environ={"SMART_PARKING_API_PORT": "9000"},
        overrides={"api": {"port": 9100}},
    )
    assert settings.api.port == 9100


def test_invalid_geometry_thresholds_fail(tmp_path: Path) -> None:
    config = tmp_path / "bad.yaml"
    config.write_text(
        "geometry:\n  occupied_enter_threshold: 0.2\n  occupied_exit_threshold: 0.3\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="occupied_exit_threshold"):
        load_settings(config)


def test_missing_config_file_fails(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_settings(tmp_path / "missing.yaml")


def test_duplicate_space_ids_fail(tmp_path: Path) -> None:
    path = tmp_path / "dup.json"
    path.write_text(
        json.dumps(
            {
                "camera_id": "cam",
                "reference_width": 100,
                "reference_height": 100,
                "spaces": [
                    {
                        "id": "A1",
                        "label": "A1",
                        "polygon": [[0, 0], [10, 0], [10, 10], [0, 10]],
                    },
                    {
                        "id": "A1",
                        "label": "A1-dup",
                        "polygon": [[20, 0], [30, 0], [30, 10], [20, 10]],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="Duplicate parking space id"):
        load_parking_map(path)


def test_too_few_polygon_points_fail(tmp_path: Path) -> None:
    path = tmp_path / "short.json"
    path.write_text(
        json.dumps(
            {
                "camera_id": "cam",
                "reference_width": 100,
                "reference_height": 100,
                "spaces": [
                    {"id": "A1", "label": "A1", "polygon": [[0, 0], [10, 0]]},
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="at least 3 points"):
        load_parking_map(path)


def test_zero_area_polygon_fails(tmp_path: Path) -> None:
    path = tmp_path / "flat.json"
    path.write_text(
        json.dumps(
            {
                "camera_id": "cam",
                "reference_width": 100,
                "reference_height": 100,
                "spaces": [
                    {
                        "id": "A1",
                        "label": "A1",
                        "polygon": [[0, 0], [10, 0], [20, 0]],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="non-positive area"):
        load_parking_map(path)


def test_point_outside_reference_fails(tmp_path: Path) -> None:
    path = tmp_path / "oob.json"
    path.write_text(
        json.dumps(
            {
                "camera_id": "cam",
                "reference_width": 50,
                "reference_height": 50,
                "spaces": [
                    {
                        "id": "A1",
                        "label": "A1",
                        "polygon": [[0, 0], [60, 0], [60, 40], [0, 40]],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="outside reference width"):
        load_parking_map(path)


def test_point_outside_reference_height_fails(tmp_path: Path) -> None:
    path = tmp_path / "oob-y.json"
    path.write_text(
        json.dumps(
            {
                "camera_id": "cam",
                "reference_width": 100,
                "reference_height": 50,
                "spaces": [
                    {
                        "id": "A1",
                        "label": "A1",
                        "polygon": [[0, 0], [40, 0], [40, 80], [0, 80]],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="outside reference height"):
        load_parking_map(path)


def test_invalid_yaml_and_root(tmp_path: Path) -> None:
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text(":\n  - broken", encoding="utf-8")
    with pytest.raises(ConfigError, match="Invalid YAML"):
        load_settings(bad_yaml)

    list_root = tmp_path / "list.yaml"
    list_root.write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="must be a mapping"):
        load_settings(list_root)

    empty = tmp_path / "empty.yaml"
    empty.write_text("", encoding="utf-8")
    settings = load_settings(empty)
    assert settings.app.environment == "development"


def test_env_bool_and_camera_id_validation(tmp_path: Path) -> None:
    config = tmp_path / "app.yaml"
    config.write_text("video:\n  display: false\n", encoding="utf-8")
    settings = load_settings(
        config,
        environ={
            "SMART_PARKING_VIDEO__DISPLAY": "true",
            "SMART_PARKING_APP__ENVIRONMENT": "test",
        },
    )
    assert settings.video.display is True
    assert settings.app.environment == "test"

    bad_cam = tmp_path / "cam.yaml"
    bad_cam.write_text("camera:\n  id: '  '\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="camera.id"):
        load_settings(bad_cam)


def test_parking_map_malformed_payloads(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    with pytest.raises(ConfigError, match="not found"):
        load_parking_map(missing)

    invalid_json = tmp_path / "bad.json"
    invalid_json.write_text("{not-json", encoding="utf-8")
    with pytest.raises(ConfigError, match="Invalid JSON"):
        load_parking_map(invalid_json)

    not_object = tmp_path / "arr.json"
    not_object.write_text("[]", encoding="utf-8")
    with pytest.raises(ConfigError, match="JSON object"):
        load_parking_map(not_object)

    bad_point = tmp_path / "point.json"
    bad_point.write_text(
        json.dumps(
            {
                "camera_id": "cam",
                "reference_width": 100,
                "reference_height": 100,
                "spaces": [
                    {"id": "A1", "label": "A1", "polygon": [[0, 0], [10], [10, 10]]},
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="must be \\[x, y\\]"):
        load_parking_map(bad_point)

    non_numeric = tmp_path / "nonnum.json"
    non_numeric.write_text(
        json.dumps(
            {
                "camera_id": "cam",
                "reference_width": 100,
                "reference_height": 100,
                "spaces": [
                    {
                        "id": "A1",
                        "label": "A1",
                        "polygon": [[0, 0], ["x", 1], [10, 10]],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="non-numeric"):
        load_parking_map(non_numeric)

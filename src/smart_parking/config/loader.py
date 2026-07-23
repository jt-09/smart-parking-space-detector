"""Configuration and parking-map loaders with layered precedence."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from smart_parking.config.models import Settings
from smart_parking.domain.parking import ParkingMap, ParkingSpace, Point

ENV_PREFIX = "SMART_PARKING_"

# Flat environment keys map onto nested Settings fields.
_ENV_ALIASES: dict[str, tuple[str, ...]] = {
    "LOG_LEVEL": ("app", "log_level"),
    "ENVIRONMENT": ("app", "environment"),
    "OUTPUT_DIR": ("app", "output_dir"),
    "CAMERA_ID": ("camera", "id"),
    "CAMERA_SOURCE": ("camera", "source"),
    "DATABASE_URL": ("persistence", "database_url"),
    "MODEL_NAME": ("model", "name"),
    "MODEL_DEVICE": ("model", "device"),
    "MODEL_CONFIDENCE": ("model", "confidence"),
    "PARKING_MAP": ("geometry", "parking_map"),
    "API_HOST": ("api", "host"),
    "API_PORT": ("api", "port"),
}


class ConfigError(ValueError):
    """Raised when configuration or parking-map validation fails."""


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overlay.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _set_nested(target: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    cursor = target
    for key in path[:-1]:
        next_value = cursor.get(key)
        if not isinstance(next_value, dict):
            next_value = {}
            cursor[key] = next_value
        cursor = next_value
    cursor[path[-1]] = value


def _coerce_env_value(raw: str) -> Any:
    lowered = raw.strip().lower()
    if lowered in {"true", "yes", "1"}:
        return True
    if lowered in {"false", "no", "0"}:
        return False
    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except ValueError:
        return raw


def _env_overrides(environ: dict[str, str] | None = None) -> dict[str, Any]:
    source = environ if environ is not None else dict(os.environ)
    overlay: dict[str, Any] = {}
    for key, value in source.items():
        if not key.startswith(ENV_PREFIX):
            continue
        suffix = key[len(ENV_PREFIX) :]
        if suffix in _ENV_ALIASES:
            _set_nested(overlay, _ENV_ALIASES[suffix], _coerce_env_value(value))
            continue
        # Nested form: SMART_PARKING_APP__LOG_LEVEL or SMART_PARKING_CAMERA__ID
        if "__" in suffix:
            parts = tuple(part.lower() for part in suffix.split("__") if part)
            if parts:
                _set_nested(overlay, parts, _coerce_env_value(value))
    return overlay


def _format_validation_error(exc: ValidationError, *, context: str) -> str:
    details = "; ".join(
        f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}" for err in exc.errors()
    )
    return f"{context}: {details}"


def load_yaml_file(path: Path) -> dict[str, Any]:
    """Load a YAML mapping from disk."""
    if not path.is_file():
        raise ConfigError(f"Configuration file not found: {path}")
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {path}: {exc}") from exc
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ConfigError(f"Configuration root in {path} must be a mapping/object.")
    return loaded


def load_settings(
    config_path: Path | str | None = None,
    *,
    environ: dict[str, str] | None = None,
    overrides: dict[str, Any] | None = None,
) -> Settings:
    """Load settings with precedence: defaults < YAML < env < overrides."""
    data: dict[str, Any] = Settings().model_dump(mode="json")

    if config_path is not None:
        yaml_data = load_yaml_file(Path(config_path))
        data = _deep_merge(data, yaml_data)

    data = _deep_merge(data, _env_overrides(environ))

    if overrides:
        data = _deep_merge(data, overrides)

    try:
        return Settings.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(_format_validation_error(exc, context="Invalid settings")) from exc


def _parse_point(raw: Any, *, space_id: str, index: int) -> Point:
    if not isinstance(raw, (list, tuple)) or len(raw) != 2:
        msg = f"Space '{space_id}' polygon point {index} must be [x, y]; got {raw!r}."
        raise ConfigError(msg)
    try:
        return Point(float(raw[0]), float(raw[1]))
    except (TypeError, ValueError) as exc:
        msg = f"Space '{space_id}' polygon point {index} has non-numeric coordinates: {raw!r}."
        raise ConfigError(msg) from exc


def _validate_space_geometry(
    space: ParkingSpace,
    *,
    reference_width: int,
    reference_height: int,
) -> None:
    if space.area <= 0.0:
        msg = (
            f"Parking space '{space.id}' polygon has non-positive area "
            f"({space.area}). Points may be collinear or duplicated; redraw the polygon."
        )
        raise ConfigError(msg)

    for index, point in enumerate(space.polygon):
        if not (0.0 <= point.x <= float(reference_width)):
            msg = (
                f"Parking space '{space.id}' point {index} x={point.x} is outside "
                f"reference width [0, {reference_width}]."
            )
            raise ConfigError(msg)
        if not (0.0 <= point.y <= float(reference_height)):
            msg = (
                f"Parking space '{space.id}' point {index} y={point.y} is outside "
                f"reference height [0, {reference_height}]."
            )
            raise ConfigError(msg)


def load_parking_map(path: Path | str) -> ParkingMap:
    """Load and validate a parking-space map JSON file."""
    map_path = Path(path)
    if not map_path.is_file():
        raise ConfigError(f"Parking map file not found: {map_path}")

    try:
        payload = json.loads(map_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in parking map {map_path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise ConfigError(f"Parking map root in {map_path} must be a JSON object.")

    camera_id = payload.get("camera_id")
    reference_width = payload.get("reference_width")
    reference_height = payload.get("reference_height")
    raw_spaces = payload.get("spaces")

    if not isinstance(camera_id, str) or not camera_id.strip():
        raise ConfigError("Parking map requires a non-empty string 'camera_id'.")
    if not isinstance(reference_width, int) or reference_width <= 0:
        raise ConfigError("Parking map 'reference_width' must be a positive integer.")
    if not isinstance(reference_height, int) or reference_height <= 0:
        raise ConfigError("Parking map 'reference_height' must be a positive integer.")
    if not isinstance(raw_spaces, list):
        raise ConfigError("Parking map 'spaces' must be a list of space objects.")

    spaces: list[ParkingSpace] = []
    seen_ids: set[str] = set()

    for index, raw in enumerate(raw_spaces):
        if not isinstance(raw, dict):
            raise ConfigError(f"Parking map spaces[{index}] must be an object.")
        space_id = raw.get("id")
        if not isinstance(space_id, str) or not space_id.strip():
            raise ConfigError(f"Parking map spaces[{index}] requires a non-empty string 'id'.")
        if space_id in seen_ids:
            msg = (
                f"Duplicate parking space id '{space_id}' in {map_path}. "
                "Each space id must be unique."
            )
            raise ConfigError(msg)
        seen_ids.add(space_id)

        label = raw.get("label", space_id)
        if not isinstance(label, str) or not label.strip():
            raise ConfigError(f"Parking space '{space_id}' label must be a non-empty string.")

        polygon_raw = raw.get("polygon")
        if not isinstance(polygon_raw, list):
            raise ConfigError(
                f"Parking space '{space_id}' requires a 'polygon' list of [x, y] points."
            )
        if len(polygon_raw) < 3:
            msg = (
                f"Parking space '{space_id}' polygon needs at least 3 points, "
                f"got {len(polygon_raw)}. Add more vertices in the parking map."
            )
            raise ConfigError(msg)

        points = tuple(
            _parse_point(item, space_id=space_id, index=point_index)
            for point_index, item in enumerate(polygon_raw)
        )

        zone = raw.get("zone")
        if zone is not None and not isinstance(zone, str):
            raise ConfigError(f"Parking space '{space_id}' zone must be a string or null.")

        enabled = raw.get("enabled", True)
        if not isinstance(enabled, bool):
            raise ConfigError(f"Parking space '{space_id}' enabled must be a boolean.")

        metadata = raw.get("metadata", {})
        if not isinstance(metadata, dict):
            raise ConfigError(f"Parking space '{space_id}' metadata must be an object.")

        try:
            space = ParkingSpace(
                id=space_id,
                label=label,
                polygon=points,
                zone=zone,
                enabled=enabled,
                metadata=metadata,
            )
        except ValueError as exc:
            raise ConfigError(str(exc)) from exc

        _validate_space_geometry(
            space,
            reference_width=reference_width,
            reference_height=reference_height,
        )
        spaces.append(space)

    try:
        return ParkingMap(
            camera_id=camera_id,
            reference_width=reference_width,
            reference_height=reference_height,
            spaces=tuple(spaces),
        )
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc

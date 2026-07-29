"""Ground-truth loading for occupancy evaluation (CSV / JSON)."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from smart_parking.domain.state import OccupancyState

_STABLE_STATES = {
    OccupancyState.AVAILABLE.value,
    OccupancyState.OCCUPIED.value,
    OccupancyState.UNKNOWN.value,
}


@dataclass(frozen=True, slots=True)
class GroundTruthLabel:
    """One expected occupancy label at a frame index or timestamp."""

    frame_or_time: float
    space_id: str
    expected_state: OccupancyState

    def __post_init__(self) -> None:
        if not self.space_id.strip():
            raise ValueError("space_id must be a non-empty string.")
        if self.expected_state.value not in _STABLE_STATES:
            msg = (
                f"expected_state must be available, occupied, or unknown; "
                f"got {self.expected_state!r}."
            )
            raise ValueError(msg)


def parse_expected_state(value: str) -> OccupancyState:
    """Parse a ground-truth state string into a stable OccupancyState."""
    text = value.strip().lower()
    try:
        state = OccupancyState(text)
    except ValueError as exc:
        msg = f"Invalid expected_state {value!r}; use available, occupied, or unknown."
        raise ValueError(msg) from exc
    if state.value not in _STABLE_STATES:
        msg = f"expected_state must be available, occupied, or unknown; got {value!r}."
        raise ValueError(msg)
    return state


def _label_from_mapping(row: dict[str, Any], *, line: int | None = None) -> GroundTruthLabel:
    missing = [k for k in ("frame_or_time", "space_id", "expected_state") if k not in row]
    if missing:
        where = f" at line {line}" if line is not None else ""
        msg = f"Ground-truth row{where} missing keys: {', '.join(missing)}."
        raise ValueError(msg)
    try:
        frame_or_time = float(row["frame_or_time"])
    except (TypeError, ValueError) as exc:
        where = f" at line {line}" if line is not None else ""
        msg = f"Invalid frame_or_time{where}: {row['frame_or_time']!r}."
        raise ValueError(msg) from exc
    space_id = str(row["space_id"]).strip()
    expected = parse_expected_state(str(row["expected_state"]))
    return GroundTruthLabel(
        frame_or_time=frame_or_time,
        space_id=space_id,
        expected_state=expected,
    )


def load_ground_truth_csv(path: Path | str) -> tuple[GroundTruthLabel, ...]:
    """Load ground-truth labels from a CSV file.

    Required columns: ``frame_or_time``, ``space_id``, ``expected_state``.
    """
    file_path = Path(path)
    with file_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header row: {file_path}")
        normalized = {name.strip().lower(): name for name in reader.fieldnames}
        required = ("frame_or_time", "space_id", "expected_state")
        missing = [name for name in required if name not in normalized]
        if missing:
            msg = f"CSV missing required columns {missing}: {file_path}"
            raise ValueError(msg)
        labels: list[GroundTruthLabel] = []
        for line_no, raw in enumerate(reader, start=2):
            row = {
                "frame_or_time": raw[normalized["frame_or_time"]],
                "space_id": raw[normalized["space_id"]],
                "expected_state": raw[normalized["expected_state"]],
            }
            if all(v is None or str(v).strip() == "" for v in row.values()):
                continue
            labels.append(_label_from_mapping(row, line=line_no))
    if not labels:
        raise ValueError(f"No ground-truth rows found in {file_path}")
    return tuple(labels)


def load_ground_truth_json(path: Path | str) -> tuple[GroundTruthLabel, ...]:
    """Load ground-truth labels from a JSON array or ``{\"labels\": [...]}`` object."""
    file_path = Path(path)
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        rows = payload.get("labels", payload.get("ground_truth"))
        if rows is None:
            raise ValueError(
                f"JSON object must contain 'labels' or 'ground_truth' array: {file_path}"
            )
    elif isinstance(payload, list):
        rows = payload
    else:
        raise ValueError(f"JSON ground truth must be a list or object: {file_path}")
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"No ground-truth rows found in {file_path}")
    labels = [_label_from_mapping(dict(row), line=index + 1) for index, row in enumerate(rows)]
    return tuple(labels)


def load_ground_truth(path: Path | str) -> tuple[GroundTruthLabel, ...]:
    """Load ground truth from CSV or JSON based on file suffix."""
    file_path = Path(path)
    suffix = file_path.suffix.lower()
    if suffix == ".csv":
        return load_ground_truth_csv(file_path)
    if suffix in {".json", ".jsonl"}:
        if suffix == ".jsonl":
            labels: list[GroundTruthLabel] = []
            for line_no, line in enumerate(
                file_path.read_text(encoding="utf-8").splitlines(),
                start=1,
            ):
                text = line.strip()
                if not text:
                    continue
                labels.append(_label_from_mapping(json.loads(text), line=line_no))
            if not labels:
                raise ValueError(f"No ground-truth rows found in {file_path}")
            return tuple(labels)
        return load_ground_truth_json(file_path)
    msg = f"Unsupported ground-truth format {suffix!r}; use .csv or .json."
    raise ValueError(msg)

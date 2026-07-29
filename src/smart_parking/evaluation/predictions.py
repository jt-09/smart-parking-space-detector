"""Load predicted occupancy labels from CSV or JSON."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from smart_parking.evaluation.ground_truth import parse_expected_state
from smart_parking.evaluation.metrics import PredictedLabel


def _row_to_prediction(row: dict[str, Any], *, line: int | None = None) -> PredictedLabel:
    missing = [k for k in ("frame_or_time", "space_id") if k not in row]
    if missing:
        where = f" at line {line}" if line is not None else ""
        msg = f"Prediction row{where} missing keys: {', '.join(missing)}."
        raise ValueError(msg)
    state_raw = row.get("predicted_state", row.get("expected_state"))
    if state_raw is None:
        where = f" at line {line}" if line is not None else ""
        msg = f"Prediction row{where} missing predicted_state (or expected_state)."
        raise ValueError(msg)
    try:
        frame_or_time = float(row["frame_or_time"])
    except (TypeError, ValueError) as exc:
        where = f" at line {line}" if line is not None else ""
        msg = f"Invalid frame_or_time{where}: {row['frame_or_time']!r}."
        raise ValueError(msg) from exc
    return PredictedLabel(
        frame_or_time=frame_or_time,
        space_id=str(row["space_id"]).strip(),
        predicted_state=parse_expected_state(str(state_raw)),
    )


def load_predictions_csv(path: Path | str) -> tuple[PredictedLabel, ...]:
    """Load predictions from CSV with frame_or_time, space_id, predicted_state."""
    file_path = Path(path)
    with file_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header row: {file_path}")
        labels = [
            _row_to_prediction(dict(row), line=line_no)
            for line_no, row in enumerate(reader, start=2)
            if any(str(v).strip() for v in row.values() if v is not None)
        ]
    if not labels:
        raise ValueError(f"No prediction rows found in {file_path}")
    return tuple(labels)


def load_predictions_json(path: Path | str) -> tuple[PredictedLabel, ...]:
    """Load predictions from a JSON array or ``{\"predictions\": [...]}`` object."""
    file_path = Path(path)
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        rows = payload.get("predictions", payload.get("labels"))
        if rows is None:
            raise ValueError(
                f"JSON object must contain 'predictions' or 'labels' array: {file_path}"
            )
    elif isinstance(payload, list):
        rows = payload
    else:
        raise ValueError(f"JSON predictions must be a list or object: {file_path}")
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"No prediction rows found in {file_path}")
    return tuple(_row_to_prediction(dict(row), line=index + 1) for index, row in enumerate(rows))


def load_predictions(path: Path | str) -> tuple[PredictedLabel, ...]:
    """Load predictions from CSV or JSON based on file suffix."""
    file_path = Path(path)
    suffix = file_path.suffix.lower()
    if suffix == ".csv":
        return load_predictions_csv(file_path)
    if suffix == ".json":
        return load_predictions_json(file_path)
    msg = f"Unsupported predictions format {suffix!r}; use .csv or .json."
    raise ValueError(msg)

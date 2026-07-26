"""CLI-level process command smoke test (synthetic + fake detector)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from smart_parking.cli.main import app

runner = CliRunner()
_CLI_ENV = {"NO_COLOR": "1", "TERM": "dumb", "COLUMNS": "120"}


def _write_map(path: Path, width: int = 64, height: int = 48) -> None:
    payload = {
        "camera_id": "cli-cam",
        "reference_width": width,
        "reference_height": height,
        "spaces": [
            {
                "id": "A1",
                "label": "A1",
                "enabled": True,
                "polygon": [[2, 8], [30, 8], [30, 40], [2, 40]],
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_cli_process_synthetic_fake(tmp_path: Path) -> None:
    map_path = tmp_path / "map.json"
    out_dir = tmp_path / "out"
    _write_map(map_path)
    result = runner.invoke(
        app,
        [
            "process",
            "--source",
            "synthetic:64:48:6",
            "--detector",
            "fake",
            "--parking-map",
            str(map_path),
            "--output-dir",
            str(out_dir),
            "--every-n",
            "1",
        ],
        env=_CLI_ENV,
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "Done." in result.stdout
    assert out_dir.is_dir()
    jsonl = list(out_dir.glob("snapshots_*.jsonl"))
    assert len(jsonl) == 1
    lines = jsonl[0].read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 6
    metrics = list(out_dir.glob("metrics_*.json"))
    assert len(metrics) == 1

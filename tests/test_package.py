"""Package smoke tests for the scaffold."""

from __future__ import annotations

import re
from pathlib import Path

from typer.testing import CliRunner

from smart_parking import __version__
from smart_parking.cli.main import app

runner = CliRunner()
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
_CLI_ENV = {"NO_COLOR": "1", "TERM": "dumb", "COLUMNS": "120"}


def _plain(text: str) -> str:
    return _ANSI_RE.sub("", text)


def test_version_is_semver_like() -> None:
    parts = __version__.split(".")
    assert len(parts) >= 2
    assert all(part.isdigit() for part in parts[:2])


def test_cli_entrypoint_runs() -> None:
    result = runner.invoke(app, [], env=_CLI_ENV)
    assert result.exit_code == 0
    assert "smart-parking" in result.stdout
    assert __version__ in result.stdout


def test_cli_help() -> None:
    result = runner.invoke(app, ["--help"], env=_CLI_ENV)
    assert result.exit_code == 0
    plain = _plain(result.stdout)
    assert "edit-spaces" in plain
    assert "process" in plain
    assert "serve" in plain
    assert "benchmark" in plain
    assert "export-events" in plain
    assert "db" in plain


def test_benchmark_help() -> None:
    result = runner.invoke(app, ["benchmark", "--help"], env=_CLI_ENV)
    assert result.exit_code == 0
    plain = _plain(result.stdout)
    assert "--frames" in plain
    assert "--report" in plain or "-o" in plain
    assert "ground-truth" in plain or "ground_truth" in plain.lower()


def test_benchmark_runs_synthetic(tmp_path: Path) -> None:
    report = tmp_path / "bench.txt"
    result = runner.invoke(
        app,
        [
            "benchmark",
            "--frames",
            "6",
            "--width",
            "64",
            "--height",
            "48",
            "--report",
            str(report),
        ],
        env=_CLI_ENV,
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    plain = _plain(result.stdout)
    assert "Throughput" in plain
    assert "e2e_fps" in plain
    assert report.is_file()
    assert "Smart Parking" in report.read_text(encoding="utf-8")


def test_benchmark_requires_predictions_with_ground_truth(tmp_path: Path) -> None:
    gt = tmp_path / "gt.csv"
    gt.write_text(
        "frame_or_time,space_id,expected_state\n0,A1,available\n",
        encoding="utf-8",
    )
    result = runner.invoke(
        app,
        ["benchmark", "--frames", "4", "--width", "64", "--height", "48", "-g", str(gt)],
        env=_CLI_ENV,
    )
    assert result.exit_code == 1
    assert "predictions" in (result.stdout + result.stderr).lower()


def test_benchmark_with_ground_truth(tmp_path: Path) -> None:
    gt = tmp_path / "gt.csv"
    pred = tmp_path / "pred.csv"
    gt.write_text(
        "frame_or_time,space_id,expected_state\n0,A1,available\n1,A1,occupied\n",
        encoding="utf-8",
    )
    pred.write_text(
        "frame_or_time,space_id,predicted_state\n0,A1,available\n1,A1,occupied\n",
        encoding="utf-8",
    )
    result = runner.invoke(
        app,
        [
            "benchmark",
            "--frames",
            "4",
            "--width",
            "64",
            "--height",
            "48",
            "-g",
            str(gt),
            "-p",
            str(pred),
        ],
        env=_CLI_ENV,
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    plain = _plain(result.stdout)
    assert "Occupancy accuracy" in plain
    assert "macro_accuracy" in plain


def test_cli_version_flag() -> None:
    result = runner.invoke(app, ["--version"], env=_CLI_ENV)
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_edit_spaces_help() -> None:
    result = runner.invoke(app, ["edit-spaces", "--help"], env=_CLI_ENV)
    assert result.exit_code == 0
    plain = _plain(result.stdout)
    assert "--source" in plain or "-s" in plain
    assert "--output" in plain or "-o" in plain
    assert "source" in plain.lower()
    assert "output" in plain.lower()


def test_process_help() -> None:
    result = runner.invoke(app, ["process", "--help"], env=_CLI_ENV)
    assert result.exit_code == 0
    plain = _plain(result.stdout)
    assert "--config" in plain or "-c" in plain
    assert "--source" in plain or "-s" in plain
    assert "process" in plain.lower()


def test_serve_help() -> None:
    result = runner.invoke(app, ["serve", "--help"], env=_CLI_ENV)
    assert result.exit_code == 0
    plain = _plain(result.stdout)
    assert "--config" in plain or "-c" in plain
    assert "--host" in plain
    assert "--port" in plain
    assert "serve" in plain.lower()

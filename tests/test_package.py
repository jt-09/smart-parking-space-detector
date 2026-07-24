"""Package smoke tests for the scaffold."""

from __future__ import annotations

from typer.testing import CliRunner

from smart_parking import __version__
from smart_parking.cli.main import app

runner = CliRunner()


def test_version_is_semver_like() -> None:
    parts = __version__.split(".")
    assert len(parts) >= 2
    assert all(part.isdigit() for part in parts[:2])


def test_cli_entrypoint_runs() -> None:
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "smart-parking" in result.stdout
    assert __version__ in result.stdout


def test_cli_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "edit-spaces" in result.stdout


def test_cli_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_edit_spaces_help() -> None:
    result = runner.invoke(app, ["edit-spaces", "--help"])
    assert result.exit_code == 0
    assert "--source" in result.stdout
    assert "--output" in result.stdout

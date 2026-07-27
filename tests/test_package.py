"""Package smoke tests for the scaffold."""

from __future__ import annotations

import re

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
    assert "export-events" in plain
    assert "db" in plain


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

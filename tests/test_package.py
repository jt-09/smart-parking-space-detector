"""Package smoke tests for the scaffold."""

from __future__ import annotations

import sys

import pytest

from smart_parking import __version__


def test_version_is_semver_like() -> None:
    parts = __version__.split(".")
    assert len(parts) >= 2
    assert all(part.isdigit() for part in parts[:2])


def test_cli_entrypoint_runs(capsys: pytest.CaptureFixture[str]) -> None:
    from smart_parking.cli.main import app

    app()
    captured = capsys.readouterr()
    assert "smart-parking" in captured.out


def test_cli_help(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    from smart_parking.cli.main import app

    monkeypatch.setattr(sys, "argv", ["smart-parking", "--help"])
    app()
    captured = capsys.readouterr()
    assert "Usage:" in captured.out

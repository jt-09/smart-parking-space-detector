"""Command-line interface entrypoints."""

from __future__ import annotations

import sys


def app() -> None:
    """Console script entrypoint.

    Full Typer commands are added in later phases. The scaffold exposes a
    stable ``smart-parking`` entry point that reports the package version.
    """
    from smart_parking import __version__

    print(f"smart-parking {__version__}")
    if len(sys.argv) > 1 and sys.argv[1] in {"-h", "--help"}:
        print("Usage: smart-parking [--help]")
        print("Commands will be added in subsequent phases.")


if __name__ == "__main__":  # pragma: no cover
    app()

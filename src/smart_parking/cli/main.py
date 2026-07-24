"""Command-line interface entrypoints."""

from __future__ import annotations

from pathlib import Path

import typer

from smart_parking import __version__

app = typer.Typer(
    name="smart-parking",
    help="Fixed-camera parking-lot occupancy detector.",
    no_args_is_help=False,
    add_completion=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"smart-parking {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """Smart Parking-Space Detector CLI."""
    if ctx.invoked_subcommand is None and not version:
        typer.echo(f"smart-parking {__version__}")
        typer.echo("Use smart-parking --help to list commands.")


@app.command("edit-spaces")
def edit_spaces(
    source: Path = typer.Option(  # noqa: B008
        ...,
        "--source",
        "-s",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Reference image or video used as the editing background.",
    ),
    output: Path = typer.Option(  # noqa: B008
        ...,
        "--output",
        "-o",
        help="Destination parking-map JSON path.",
    ),
    camera_id: str = typer.Option(
        "camera-01",
        "--camera-id",
        help="Camera id written into a new parking map.",
    ),
    existing: Path | None = typer.Option(  # noqa: B008
        None,
        "--existing",
        "-e",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Optional existing parking-map JSON to reload and edit.",
    ),
    scale_to_source: bool = typer.Option(
        True,
        "--scale-to-source/--no-scale-to-source",
        help="Scale an existing map when its reference resolution differs from the source.",
    ),
) -> None:
    """Interactively draw and validate parking-space polygons."""
    from smart_parking.tools.polygon_editor import run_polygon_editor

    try:
        path = run_polygon_editor(
            source=source,
            output=output,
            camera_id=camera_id,
            existing_map=existing,
            scale_to_source=scale_to_source,
        )
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.secho(f"Parking map written to {path}", fg=typer.colors.GREEN)


if __name__ == "__main__":  # pragma: no cover
    app()

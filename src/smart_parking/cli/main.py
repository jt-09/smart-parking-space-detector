"""Command-line interface entrypoints."""

from __future__ import annotations

import logging
import signal
import uuid
from pathlib import Path
from typing import Any

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


@app.command("process")
def process_command(
    config: Path | None = typer.Option(  # noqa: B008
        None,
        "--config",
        "-c",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Optional YAML settings file (defaults + env still apply).",
    ),
    source: str | None = typer.Option(
        None,
        "--source",
        "-s",
        help="Frame source path, webcam index, URI, or 'synthetic'. Overrides config.",
    ),
    output_dir: Path | None = typer.Option(  # noqa: B008
        None,
        "--output-dir",
        "-o",
        help="Directory for annotated video and JSONL snapshots.",
    ),
    parking_map: Path | None = typer.Option(  # noqa: B008
        None,
        "--parking-map",
        "-m",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Parking-map JSON path (overrides config geometry.parking_map).",
    ),
    detector: str | None = typer.Option(
        None,
        "--detector",
        help="Detector backend: 'ultralytics' (default) or 'fake' (no weights).",
    ),
    save_video: bool | None = typer.Option(
        None,
        "--save-video/--no-save-video",
        help="Write annotated MP4 under the output directory.",
    ),
    every_n: int | None = typer.Option(
        None,
        "--every-n",
        min=1,
        help="Process every Nth frame (overrides video.process_every_n_frames).",
    ),
) -> None:
    """Run the end-to-end occupancy pipeline on a video or camera source."""
    from smart_parking.config.loader import ConfigError, load_parking_map, load_settings
    from smart_parking.detection.base import Detector
    from smart_parking.detection.fake import FakeDetector, default_fake_detections
    from smart_parking.pipeline.processor import ParkingProcessor, create_detector
    from smart_parking.pipeline.writers import (
        AnnotatedVideoWriter,
        JsonlSnapshotWriter,
        build_output_paths,
        write_metrics_json,
    )
    from smart_parking.rendering.renderer import AnnotationRenderer
    from smart_parking.sources.base import ReconnectPolicy
    from smart_parking.sources.factory import create_frame_source

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    overrides: dict[str, Any] = {}
    if source is not None:
        overrides.setdefault("camera", {})["source"] = source
    if output_dir is not None:
        overrides.setdefault("app", {})["output_dir"] = str(output_dir)
    if parking_map is not None:
        overrides.setdefault("geometry", {})["parking_map"] = str(parking_map)
    if save_video is not None:
        overrides.setdefault("video", {})["save_annotated_video"] = save_video
    if every_n is not None:
        overrides.setdefault("video", {})["process_every_n_frames"] = every_n
    if detector is not None and detector.strip().lower() == "fake":
        overrides.setdefault("model", {})["name"] = "fake"

    try:
        settings = load_settings(config, overrides=overrides or None)
        map_path = parking_map if parking_map is not None else settings.geometry.parking_map
        parking = load_parking_map(map_path)
    except ConfigError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    source_spec: str | int = settings.camera.source
    if isinstance(source_spec, str) and source_spec.isdigit():
        source_spec = int(source_spec)

    frame_source = create_frame_source(
        source_spec,
        source_id=settings.camera.id,
        reconnect=ReconnectPolicy(delay_seconds=settings.camera.reconnect_seconds),
    )

    if settings.model.name.strip().lower() in {"fake", "none", "stub"}:
        det: Detector = FakeDetector(default_fake_detections(), device=settings.model.device)
    else:
        det = create_detector(settings)

    run_id = str(uuid.uuid4())
    paths = build_output_paths(settings.app.output_dir, run_id=run_id)
    fps = settings.video.output_fps if settings.video.output_fps is not None else 10.0
    video_writer: AnnotatedVideoWriter | None = None
    jsonl_writer: JsonlSnapshotWriter | None = None

    if settings.video.save_annotated_video:
        video_writer = AnnotatedVideoWriter(paths["annotated_video"], fps=fps)
    jsonl_writer = JsonlSnapshotWriter(paths["snapshots_jsonl"])

    processor = ParkingProcessor(
        settings,
        parking,
        frame_source,
        det,
        run_id=run_id,
        render_fn=AnnotationRenderer(),
        annotated_sink=video_writer,
        snapshot_sink=jsonl_writer,
    )

    def _handle_sigint(signum: int, frame: object) -> None:
        del signum, frame
        typer.secho("Stop requested — finishing current frame…", err=True)
        processor.request_stop()

    previous = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, _handle_sigint)
    try:
        try:
            result = processor.run()
        except (RuntimeError, ValueError, OSError) as exc:
            typer.secho(str(exc), fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1) from exc
    finally:
        signal.signal(signal.SIGINT, previous)
        # Processor.run() already closes sinks + source; close again is idempotent.
        if video_writer is not None:
            video_writer.close()
        if jsonl_writer is not None:
            jsonl_writer.close()
        frame_source.close()

    write_metrics_json(
        paths["metrics_json"],
        result.metrics,
        run_id=result.run_id,
        interrupted=result.interrupted,
    )

    summary = (
        f"run={result.run_id} processed={result.metrics.frames_processed} "
        f"e2e_fps={result.metrics.e2e_fps:.2f} output={paths['dir']}"
    )
    if result.interrupted:
        typer.secho(f"Interrupted. {summary}", fg=typer.colors.YELLOW)
    else:
        typer.secho(f"Done. {summary}", fg=typer.colors.GREEN)
    if video_writer is not None:
        typer.echo(f"Annotated video: {paths['annotated_video']}")
    typer.echo(f"Snapshots JSONL: {paths['snapshots_jsonl']}")


if __name__ == "__main__":  # pragma: no cover
    app()

"""Command-line interface entrypoints."""

from __future__ import annotations

import logging
import signal
import uuid
from datetime import UTC, datetime
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
db_app = typer.Typer(help="Database schema and retention commands.")
app.add_typer(db_app, name="db")


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


def _parse_iso_datetime(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _open_repository(database_url: str) -> Any:
    from smart_parking.persistence.db import create_db_engine, init_schema, make_session_factory
    from smart_parking.persistence.repository import SqlAlchemyEventRepository

    engine = create_db_engine(database_url)
    init_schema(engine)
    return SqlAlchemyEventRepository(make_session_factory(engine))


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
    persist: bool | None = typer.Option(
        None,
        "--persist/--no-persist",
        help="Persist occupancy events to SQLite (overrides persistence.enabled).",
    ),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="SQLAlchemy database URL (overrides persistence.database_url).",
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
    if persist is not None:
        overrides.setdefault("persistence", {})["enabled"] = persist
    if database_url is not None:
        overrides.setdefault("persistence", {})["database_url"] = database_url

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

    event_repository = None
    if settings.persistence.enabled:
        event_repository = _open_repository(settings.persistence.database_url)

    processor = ParkingProcessor(
        settings,
        parking,
        frame_source,
        det,
        run_id=run_id,
        render_fn=AnnotationRenderer(),
        annotated_sink=video_writer,
        snapshot_sink=jsonl_writer,
        event_repository=event_repository,
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
    if settings.persistence.enabled:
        typer.echo(f"Events database: {settings.persistence.database_url}")


@app.command("serve")
def serve_command(
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
    host: str | None = typer.Option(
        None,
        "--host",
        help="Bind host (default: settings.api.host, typically 127.0.0.1).",
    ),
    port: int | None = typer.Option(
        None,
        "--port",
        min=1,
        max=65535,
        help="Bind port (default: settings.api.port, typically 8000).",
    ),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="SQLAlchemy database URL override for analytics endpoints.",
    ),
) -> None:
    """Serve the status API and lightweight dashboard (localhost by default)."""
    import uvicorn

    from smart_parking.api.app import create_app
    from smart_parking.api.runtime import StatusStore, source_status_from_settings
    from smart_parking.config.loader import ConfigError, load_settings

    overrides: dict[str, Any] = {}
    if host is not None:
        overrides.setdefault("api", {})["host"] = host
    if port is not None:
        overrides.setdefault("api", {})["port"] = port
    if database_url is not None:
        overrides.setdefault("persistence", {})["database_url"] = database_url
        overrides.setdefault("persistence", {})["enabled"] = True

    try:
        settings = load_settings(config, overrides=overrides or None)
    except ConfigError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    repository = None
    if settings.persistence.enabled or database_url is not None:
        repository = _open_repository(settings.persistence.database_url)

    store = StatusStore(source=source_status_from_settings(settings))
    app = create_app(settings=settings, store=store, repository=repository)

    bind_host = settings.api.host
    bind_port = settings.api.port
    typer.secho(
        f"Serving Smart Parking API on http://{bind_host}:{bind_port}/ "
        f"(docs at /docs). Separate-process mode: publish snapshots via "
        f"the process command with persistence, or inject state in tests.",
        fg=typer.colors.GREEN,
    )
    uvicorn.run(app, host=bind_host, port=bind_port, log_level="info")


@app.command("benchmark")
def benchmark_command(
    frames: int = typer.Option(
        60,
        "--frames",
        min=1,
        help="Synthetic frame count for the throughput trial.",
    ),
    width: int = typer.Option(
        320,
        "--width",
        min=16,
        help="Synthetic frame width.",
    ),
    height: int = typer.Option(
        240,
        "--height",
        min=16,
        help="Synthetic frame height.",
    ),
    report: Path | None = typer.Option(  # noqa: B008
        None,
        "--report",
        "-o",
        help="Optional path for the plain-text benchmark report.",
    ),
    ground_truth: Path | None = typer.Option(  # noqa: B008
        None,
        "--ground-truth",
        "-g",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Optional ground-truth CSV/JSON for occupancy metrics.",
    ),
    predictions: Path | None = typer.Option(  # noqa: B008
        None,
        "--predictions",
        "-p",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Optional predictions CSV/JSON aligned to ground truth.",
    ),
    match_tolerance: float = typer.Option(
        0.0,
        "--match-tolerance",
        help="Max |frame_or_time| delta when pairing predictions to labels.",
    ),
) -> None:
    """Measure synthetic FakeDetector throughput and optional occupancy metrics."""
    from smart_parking.evaluation.ground_truth import load_ground_truth
    from smart_parking.evaluation.metrics import evaluate_occupancy
    from smart_parking.evaluation.predictions import load_predictions
    from smart_parking.evaluation.report import format_benchmark_report, write_benchmark_report
    from smart_parking.evaluation.throughput import run_throughput_benchmark

    try:
        throughput = run_throughput_benchmark(
            frame_count=frames,
            width=width,
            height=height,
        )
        occupancy = None
        if ground_truth is not None:
            if predictions is None:
                typer.secho(
                    "--predictions is required when --ground-truth is set.",
                    fg=typer.colors.RED,
                    err=True,
                )
                raise typer.Exit(code=1)
            occupancy = evaluate_occupancy(
                load_ground_truth(ground_truth),
                load_predictions(predictions),
                match_tolerance=match_tolerance,
            )
        text = format_benchmark_report(
            throughput=throughput,
            occupancy=occupancy,
            notes=[
                "Default throughput path uses FakeDetector (no YOLO download).",
                "Synthetic accuracy is not a real-footage acceptance claim.",
            ],
        )
    except (OSError, ValueError, RuntimeError) as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(text)
    if report is not None:
        dest = write_benchmark_report(report, text)
        typer.secho(f"Report written to {dest}", fg=typer.colors.GREEN)


@app.command("export-events")
def export_events_command(
    output: Path = typer.Option(  # noqa: B008
        ...,
        "--output",
        "-o",
        help="Destination CSV or JSON path.",
    ),
    format: str = typer.Option(  # noqa: A002
        "csv",
        "--format",
        "-f",
        help="Export format: csv or json.",
    ),
    config: Path | None = typer.Option(  # noqa: B008
        None,
        "--config",
        "-c",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Optional YAML settings file for database_url.",
    ),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="SQLAlchemy database URL override.",
    ),
    space_id: str | None = typer.Option(
        None,
        "--space-id",
        help="Optional parking-space id filter.",
    ),
    run_id: str | None = typer.Option(
        None,
        "--run-id",
        help="Optional processing-run id filter.",
    ),
) -> None:
    """Export occupancy events from SQLite to CSV or JSON."""
    from smart_parking.config.loader import ConfigError, load_settings
    from smart_parking.persistence.export import export_events_csv, export_events_json

    try:
        settings = load_settings(
            config,
            overrides={"persistence": {"database_url": database_url}} if database_url else None,
        )
    except ConfigError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    url = database_url or settings.persistence.database_url
    repo = _open_repository(url)
    events = repo.list_events(space_id=space_id, run_id=run_id)
    fmt = format.strip().lower()
    try:
        if fmt == "csv":
            path = export_events_csv(events, output)
        elif fmt == "json":
            path = export_events_json(events, output)
        else:
            typer.secho("format must be 'csv' or 'json'.", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)
    except OSError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    typer.secho(f"Exported {len(events)} events to {path}", fg=typer.colors.GREEN)


@db_app.command("migrate")
def db_migrate(
    config: Path | None = typer.Option(  # noqa: B008
        None,
        "--config",
        "-c",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Optional YAML settings file for database_url.",
    ),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="SQLAlchemy database URL override.",
    ),
) -> None:
    """Create SQLite tables if they do not already exist."""
    from smart_parking.config.loader import ConfigError, load_settings
    from smart_parking.persistence.db import migrate

    try:
        settings = load_settings(
            config,
            overrides={"persistence": {"database_url": database_url}} if database_url else None,
        )
    except ConfigError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    url = database_url or settings.persistence.database_url
    migrate(url)
    typer.secho(f"Schema ready at {url}", fg=typer.colors.GREEN)


@db_app.command("purge")
def db_purge(
    before: str = typer.Option(
        ...,
        "--before",
        help="Delete occupancy events confirmed before this ISO-8601 timestamp (UTC).",
    ),
    config: Path | None = typer.Option(  # noqa: B008
        None,
        "--config",
        "-c",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Optional YAML settings file for database_url.",
    ),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="SQLAlchemy database URL override.",
    ),
) -> None:
    """Delete occupancy events older than the given timestamp."""
    from smart_parking.config.loader import ConfigError, load_settings

    try:
        cutoff = _parse_iso_datetime(before)
        settings = load_settings(
            config,
            overrides={"persistence": {"database_url": database_url}} if database_url else None,
        )
    except (ConfigError, ValueError) as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    url = database_url or settings.persistence.database_url
    repo = _open_repository(url)
    deleted = repo.purge_before(cutoff)
    typer.secho(
        f"Purged {deleted} occupancy events confirmed before {cutoff.isoformat()}",
        fg=typer.colors.GREEN,
    )


if __name__ == "__main__":  # pragma: no cover
    app()

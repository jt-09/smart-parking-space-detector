"""End-to-end parking video processing orchestration."""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from smart_parking.config.models import Settings
from smart_parking.detection.base import Detector
from smart_parking.detection.fake import FakeDetector, default_fake_detections
from smart_parking.detection.ultralytics_detector import UltralyticsDetector
from smart_parking.domain.parking import Detection, ParkingMap
from smart_parking.domain.state import Clock, OccupancySnapshot, SystemClock
from smart_parking.geometry.assignment import SpaceAssignment, assign_detections, map_for_frame
from smart_parking.occupancy.engine import OccupancyEngine
from smart_parking.persistence.events import EventService
from smart_parking.persistence.repository import EventRepository
from smart_parking.pipeline.snapshot import PipelineMetrics
from smart_parking.sources.base import Frame, FrameSource, FrameSourceEOF

logger = logging.getLogger(__name__)

# Optional hooks keep renderer / writers out of the core loop contract.
RenderFn = Callable[
    [Any, ParkingMap, OccupancySnapshot, tuple[Detection, ...], PipelineMetrics],
    Any,
]
AnnotatedSink = Callable[[Any, OccupancySnapshot, PipelineMetrics], None]
SnapshotSink = Callable[[OccupancySnapshot, PipelineMetrics], None]


@dataclass(slots=True)
class FrameProcessResult:
    """Per-processed-frame outputs from the orchestration loop."""

    frame: Frame
    detections: tuple[Detection, ...]
    assignments: tuple[SpaceAssignment, ...]
    snapshot: OccupancySnapshot
    annotated: Any | None = None


@dataclass(slots=True)
class PipelineResult:
    """Summary returned after a processing run completes or is interrupted."""

    run_id: str
    metrics: PipelineMetrics
    final_snapshot: OccupancySnapshot | None = None
    interrupted: bool = False
    output_dir: Path | None = None
    snapshots: list[OccupancySnapshot] = field(default_factory=list)


def create_detector(settings: Settings) -> Detector:
    """Build a detector from settings (``fake`` model name skips Ultralytics)."""
    name = settings.model.name.strip().lower()
    if name in {"fake", "none", "stub"}:
        return FakeDetector(default_fake_detections(), device=settings.model.device)
    return UltralyticsDetector(
        model_name=settings.model.name,
        device=settings.model.device,
        confidence=settings.model.confidence,
        iou=settings.model.iou,
        allowed_classes=settings.model.allowed_classes,
        tracking_enabled=settings.model.tracking_enabled,
        tracker=settings.model.tracker,
    )


class ParkingProcessor:
    """Orchestrate frame source → detector → geometry → occupancy → outputs.

    Business logic stays in geometry / occupancy modules. The processor only
    wires stages, applies frame sampling, tracks metrics, and guarantees
    capture / writer cleanup on EOF, Ctrl+C, or writer failure.
    """

    def __init__(
        self,
        settings: Settings,
        parking_map: ParkingMap,
        source: FrameSource,
        detector: Detector,
        *,
        clock: Clock | None = None,
        run_id: str | None = None,
        render_fn: RenderFn | None = None,
        annotated_sink: AnnotatedSink | None = None,
        snapshot_sink: SnapshotSink | None = None,
        on_frame: Callable[[FrameProcessResult], None] | None = None,
        event_repository: EventRepository | None = None,
    ) -> None:
        self._settings = settings
        self._parking_map = parking_map
        self._source = source
        self._detector = detector
        self._clock: Clock = clock if clock is not None else SystemClock()
        self._run_id = run_id or str(uuid.uuid4())
        self._render_fn = render_fn
        self._annotated_sink = annotated_sink
        self._snapshot_sink = snapshot_sink
        self._on_frame = on_frame
        self._event_repository = event_repository
        self._event_service: EventService | None = None
        if event_repository is not None:
            self._event_service = EventService(
                repository=event_repository,
                run_id=self._run_id,
                snapshot_interval_seconds=settings.persistence.snapshot_interval_seconds,
            )
        self._engine = OccupancyEngine(
            parking_map,
            geometry=settings.geometry,
            state=settings.state,
            clock=self._clock,
        )
        self._metrics = PipelineMetrics()
        self._stop_requested = False

    @property
    def run_id(self) -> str:
        return self._run_id

    @property
    def metrics(self) -> PipelineMetrics:
        return self._metrics

    @property
    def engine(self) -> OccupancyEngine:
        return self._engine

    def request_stop(self) -> None:
        """Signal the run loop to exit after the current frame (Ctrl+C)."""
        self._stop_requested = True

    def process_frame(self, frame: Frame) -> FrameProcessResult:
        """Run detection → assignment → occupancy for a single frame."""
        t0 = time.perf_counter()
        batch = self._detector.detect(frame.image, frame_index=frame.metadata.index)
        inference_ms = batch.inference_ms
        if inference_ms is None:
            inference_ms = (time.perf_counter() - t0) * 1000.0
        self._metrics.last_inference_ms = float(inference_ms)

        detections = batch.detections
        aligned_map = map_for_frame(
            self._parking_map,
            frame_width=frame.metadata.width,
            frame_height=frame.metadata.height,
        )
        assignments = assign_detections(
            detections,
            aligned_map,
            self._settings.geometry,
            frame_width=None,
            frame_height=None,
        )
        snapshot = self._engine.update_assignments(
            assignments,
            frame_valid=True,
            camera_id=self._settings.camera.id,
            frame_index=frame.metadata.index,
            observed_at=frame.metadata.timestamp,
            run_id=self._run_id,
        )

        annotated = None
        if self._render_fn is not None:
            annotated = self._render_fn(
                frame.image,
                aligned_map,
                snapshot,
                detections,
                self._metrics,
            )

        result = FrameProcessResult(
            frame=frame,
            detections=detections,
            assignments=tuple(assignments),
            snapshot=snapshot,
            annotated=annotated,
        )
        if self._on_frame is not None:
            self._on_frame(result)
        return result

    def run(self) -> PipelineResult:
        """Process frames until EOF, stop request, or unrecoverable error."""
        metrics = self._metrics
        snapshots: list[OccupancySnapshot] = []
        final_snapshot: OccupancySnapshot | None = None
        interrupted = False
        started = time.perf_counter()
        every_n = self._settings.video.process_every_n_frames
        output_dir = Path(self._settings.app.output_dir)

        try:
            self._start_run()
            if not self._source.is_open:
                self._source.open()

            while not self._stop_requested:
                try:
                    frame = self._source.read()
                except FrameSourceEOF:
                    break
                if frame is None:
                    break

                metrics.frames_read += 1
                # Sample: process frame indices 0, N, 2N, ...
                if (frame.metadata.index % every_n) != 0:
                    metrics.frames_skipped += 1
                    continue

                try:
                    result = self.process_frame(frame)
                except Exception:
                    logger.exception(
                        "Failed processing frame %s; continuing if possible.",
                        frame.metadata.index,
                    )
                    raise

                metrics.frames_processed += 1
                final_snapshot = result.snapshot
                snapshots.append(result.snapshot)

                elapsed = max(time.perf_counter() - started, 1e-9)
                metrics.elapsed_seconds = elapsed
                metrics.decode_fps = metrics.frames_read / elapsed
                metrics.e2e_fps = metrics.frames_processed / elapsed
                if metrics.last_inference_ms and metrics.last_inference_ms > 0:
                    metrics.inference_fps = 1000.0 / metrics.last_inference_ms

                if self._annotated_sink is not None and result.annotated is not None:
                    self._annotated_sink(result.annotated, result.snapshot, metrics)
                if self._snapshot_sink is not None:
                    self._snapshot_sink(result.snapshot, metrics)
                if self._event_service is not None:
                    self._event_service.handle_snapshot(result.snapshot)

        except KeyboardInterrupt:
            interrupted = True
            logger.info("Interrupted by KeyboardInterrupt; shutting down gracefully.")
            self._stop_requested = True
        except Exception as exc:
            self._finish_run(status="failed", error_message=str(exc))
            raise
        finally:
            metrics.elapsed_seconds = max(time.perf_counter() - started, 0.0)
            self._close_safely()

        if interrupted or self._stop_requested:
            interrupted = True
            self._finish_run(status="interrupted")
        else:
            self._finish_run(status="completed")

        return PipelineResult(
            run_id=self._run_id,
            metrics=metrics,
            final_snapshot=final_snapshot,
            interrupted=interrupted,
            output_dir=output_dir,
            snapshots=snapshots,
        )

    def _start_run(self) -> None:
        if self._event_repository is None:
            return
        now = self._clock.now()
        source_fp = getattr(self._source, "source_id", None) or str(
            getattr(self._source, "uri", self._settings.camera.source)
        )
        config_json = json.dumps(
            {
                "camera_id": self._settings.camera.id,
                "model": self._settings.model.name,
                "process_every_n_frames": self._settings.video.process_every_n_frames,
            }
        )
        self._event_repository.start_run(
            run_id=self._run_id,
            camera_id=self._settings.camera.id,
            source_fingerprint=str(source_fp),
            started_at=now,
            model_name=self._settings.model.name,
            model_version=None,
            config_json=config_json,
        )
        self._event_repository.sync_parking_spaces(self._parking_map, now=now)

    def _finish_run(self, *, status: str, error_message: str | None = None) -> None:
        if self._event_repository is None:
            return
        # Avoid double-finish if fail path already ran.
        existing = self._event_repository.get_run(self._run_id)
        if existing is not None and existing.status != "running":
            return
        ended_at = self._clock.now()
        frames_read = self._metrics.frames_read
        frames_processed = self._metrics.frames_processed
        if status == "completed":
            self._event_repository.complete_run(
                self._run_id,
                ended_at=ended_at,
                frames_read=frames_read,
                frames_processed=frames_processed,
            )
        elif status == "interrupted":
            self._event_repository.interrupt_run(
                self._run_id,
                ended_at=ended_at,
                frames_read=frames_read,
                frames_processed=frames_processed,
            )
        else:
            self._event_repository.fail_run(
                self._run_id,
                ended_at=ended_at,
                error_message=error_message or "processing failed",
                frames_read=frames_read,
                frames_processed=frames_processed,
            )

    def _close_safely(self) -> None:
        """Release sinks then capture — never leave the source open."""
        for closer_name, closer in (
            ("annotated_sink", getattr(self._annotated_sink, "close", None)),
            ("snapshot_sink", getattr(self._snapshot_sink, "close", None)),
        ):
            if closer is None:
                continue
            try:
                closer()
            except Exception:
                logger.exception("Failed closing %s.", closer_name)
        try:
            self._source.close()
        except Exception:
            logger.exception("Failed closing frame source.")

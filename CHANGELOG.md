# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Autonomous agent bootstrap kit and Phase 0 project scaffold.
- Developmental commit timeline window documented as 2026-07-22 through 2026-07-28 (+10:00).
- Typed domain models for bounding boxes, detections, parking maps, occupancy
  states/snapshots, and occupancy events (UTC clock abstraction included).
- Layered Pydantic application settings with YAML / environment / override
  precedence, example config, and validated parking-map loading.
- Configuration guide documenting precedence and secret handling.
- FrameSource protocol with UTC frame metadata, reconnect policy, and
  credential redaction helpers.
- OpenCV capture adapter for image, video, webcam, and stream sources with
  bounded reconnect and resource cleanup; SyntheticFrameSource for deterministic tests.
- Parking-map JSON serialization, coordinate scaling helpers, and self-intersection
  validation (no Shapely dependency).
- OpenCV parking-space polygon editor with headless `ParkingMapEditor` core and
  Typer `edit-spaces` CLI command; see `docs/editor.md`.
- Detector protocol and `DetectionBatch` normalized outputs; Ultralytics YOLO
  adapter with configurable model/device/confidence/IoU/class filter and optional
  persistent track IDs; `FakeDetector` for weight-free tests; see `docs/detection.md`.
- Geometry engine with Shapely overlap metrics, weighted occupancy scoring,
  footprint height ratio, coordinate scaling, and deterministic one-to-one
  vehicle-to-space assignment; see `docs/geometry.md`.
- Temporal occupancy state machine with enter/exit hysteresis, frame- and
  time-based confirmation, unknown recovery, bounded evidence history, and an
  occupancy engine that wires assignment scores to per-space machines; see
  `docs/state.md`.
- End-to-end processing pipeline: frame sampling, detection, geometry
  assignment, occupancy engine, annotation renderer, annotated video + JSONL
  snapshot writers, FPS metrics, graceful Ctrl+C/EOF shutdown, and
  `smart-parking process` CLI; see `docs/pipeline.md`.
- SQLite event persistence with SQLAlchemy models for processing runs,
  parking spaces, occupancy events (unique idempotency keys), and optional
  snapshots; duration/turnover/hourly analytics; `export-events`,
  `db migrate`, and `db purge` CLI commands; optional pipeline injection
  via `persistence.enabled` / `--persist`; see `docs/persistence.md`.
- FastAPI status API and Jinja2 dashboard: `/health`, `/api/v1` status/
  spaces/events/analytics/runs endpoints, `smart-parking serve`, localhost
  bind by default, injectable snapshot/repository for weight-free tests;
  see `docs/api.md`.
- Occupancy evaluation metrics (per-space / macro accuracy, occupied
  precision-recall-F1, transition precision/recall, false flips, latency)
  plus synthetic FakeDetector throughput/memory benchmarks via
  `smart-parking benchmark` and `scripts/benchmark.py`; see `docs/evaluation.md`.

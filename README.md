# Smart Parking-Space Detector

Fixed-camera parking-lot occupancy detection for portfolio and educational use.

> **License note:** This repository is **AGPL-3.0**. The default detector stack
> (Ultralytics YOLO) is also AGPL-3.0 for open-source use. Commercial or
> closed-source redistribution requires independent licensing review of both
> this project and its dependencies. This is not legal advice.

## Status

Core pipeline, persistence, and API/dashboard are on `main`. Evaluation and
throughput benchmarks land in Phase 8. See [`SETUP.md`](SETUP.md) for the full
delivery plan and [`AGENTS.md`](AGENTS.md) for autonomous agent rules.

**Developmental commit window:** 2026-07-22 through 2026-07-28 (`+10:00`).

## Quick start (after Phase 0)

```bash
uv sync --locked --all-groups
uv run smart-parking --help
uv run smart-parking benchmark --frames 60
```

Synthetic media is used for tests and the default demo. Never commit footage,
model weights, credentials, databases, or generated videos.

Accuracy and FPS claims must cite [`docs/evaluation.md`](docs/evaluation.md)
(hardware, config, and whether results are synthetic-only). Real-footage
acceptance targets (for example 90%+) are **not** claimed from the default
FakeDetector path.

## Documentation

- [`SETUP.md`](SETUP.md) — end-to-end implementation runbook
- [`AGENTS.md`](AGENTS.md) — agent execution rules and commit timeline
- [`HUMAN_BOOTSTRAP.md`](HUMAN_BOOTSTRAP.md) — owner one-time setup
- [`docs/development-timeline.md`](docs/development-timeline.md) — commit proposals
- [`docs/configuration.md`](docs/configuration.md) — settings precedence
- [`docs/detection.md`](docs/detection.md) — YOLO models, devices, licensing
- [`docs/editor.md`](docs/editor.md) — parking map polygon editor
- [`docs/evaluation.md`](docs/evaluation.md) — occupancy metrics and throughput benchmarks
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — contribution workflow
- [`SECURITY.md`](SECURITY.md) — vulnerability reporting

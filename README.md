# Smart Parking-Space Detector

Fixed-camera parking-lot occupancy detection for portfolio and educational use.

> **License note:** This repository is **AGPL-3.0**. The default detector stack
> (Ultralytics YOLO) is also AGPL-3.0 for open-source use. Commercial or
> closed-source redistribution requires independent licensing review of both
> this project and its dependencies. This is not legal advice.

## Status

Phase 0 scaffold in progress. See [`SETUP.md`](SETUP.md) for the full delivery plan
and [`AGENTS.md`](AGENTS.md) for autonomous agent rules.

**Developmental commit window:** 2026-07-22 through 2026-07-28 (`+10:00`).

## Quick start (after Phase 0)

```bash
uv sync --locked --all-groups
uv run smart-parking --help
```

Synthetic media is used for tests and the default demo. Never commit footage,
model weights, credentials, databases, or generated videos.

## Documentation

- [`SETUP.md`](SETUP.md) — end-to-end implementation runbook
- [`AGENTS.md`](AGENTS.md) — agent execution rules and commit timeline
- [`HUMAN_BOOTSTRAP.md`](HUMAN_BOOTSTRAP.md) — owner one-time setup
- [`docs/development-timeline.md`](docs/development-timeline.md) — commit proposals
- [`docs/configuration.md`](docs/configuration.md) — settings precedence
- [`docs/detection.md`](docs/detection.md) — YOLO models, devices, licensing
- [`docs/editor.md`](docs/editor.md) — parking map polygon editor
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — contribution workflow
- [`SECURITY.md`](SECURITY.md) — vulnerability reporting

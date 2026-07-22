# Contributing

Thanks for contributing to the Smart Parking-Space Detector.

## Development setup

```bash
uv sync --locked --all-groups
uv run pre-commit install
```

Python 3.11 is required. Do not hand-create a virtual environment; `uv` manages `.venv`.

## Workflow

1. Open or reference a GitHub issue.
2. Branch from updated `main` using the names in `SETUP.md`.
3. Plan commits with the developmental commit timeline skill inside the owner window **2026-07-22 through 2026-07-28 (+10:00)** when continuing this autonomous delivery history; otherwise use current timestamps.
4. Keep commits conventional and incremental.
5. Run the local quality gate before opening a PR:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest --cov=smart_parking --cov-fail-under=85
```

6. Prefer rebase merge. Do not push feature work directly to `main`.

## Synthetic media only by default

Use deterministic synthetic parking-lot video and fake detections for tests and the default demo. Never commit footage, datasets, model weights, credentials, databases, or generated output media.

## Licensing

This repository is licensed under AGPL-3.0. Ultralytics YOLO dependencies also use AGPL-3.0 for their open-source distribution. Commercial or closed-source redistribution requires independent licensing review.

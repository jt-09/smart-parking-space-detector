# Deployment and operations

Operational notes for running Smart Parking-Space Detector outside a developer laptop.

## Recommended topologies

1. **Local demo (default)** — `uv run smart-parking process --detector fake --source synthetic` then optionally `serve` on `127.0.0.1`.
2. **Split processes** — one `process --persist` writer and one `serve` reader sharing the same SQLite URL.
3. **Container** — single image serving the API; mount config, parking map, and `output/` as volumes.

## Configuration

- Start from `configs/app.example.yaml` and `configs/parking_spaces.example.json`.
- Override with env vars prefixed `SMART_PARKING_` (see `.env.example`).
- Never commit real RTSP passwords, `.env`, model weights, footage, or databases.

## Container quick start

```bash
docker build -t smart-parking:local .
docker run --rm -p 8000:8000 \
  -v "${PWD}/configs:/app/configs:ro" \
  -v "${PWD}/output:/app/output" \
  smart-parking:local
curl -fsS http://127.0.0.1:8000/health
```

Synthetic processing without YOLO weights:

```bash
docker run --rm \
  -v "${PWD}/output:/app/output" \
  smart-parking:local \
  process --detector fake --source synthetic:64:48:12 --no-save-video
```

### OpenCV in containers

Developer installs use `opencv-python` (GUI-capable for the polygon editor). The Dockerfile installs the locked dependency tree, then **replaces** `opencv-python` with `opencv-python-headless` so both wheels are never present in the same environment. Do not install both packages together.

### Non-root execution

The image runs as UID/GID `10001` (`app`). Writable paths are `/app/output` (and optionally mounted volumes). The `HEALTHCHECK` probes `GET /health`.

## Secrets and scanning

- Prefer GitHub secret scanning and push protection on the remote repository when the plan allows it.
- Dependabot updates `uv` dependencies and GitHub Actions weekly (`.github/dependabot.yml`).
- CodeQL analyzes Python on push/PR to `main` plus a weekly schedule (`.github/workflows/codeql.yml`).
- Report vulnerabilities privately per `SECURITY.md` — do not file public issues for exploitable flaws.

## Branch protection

`main` requires status checks: `quality`, `unit-tests`, `integration-tests`, and `build`. Merges use rebase only with linear history. Feature work never pushes directly to `main`.

## Smoke validation

After deploy or a clean clone:

```bash
uv sync --locked --all-groups
uv run python scripts/smoke_test.py
```

The smoke script checks package import, example config load, a short FakeDetector synthetic pipeline, and FastAPI TestClient health/status — no camera or YOLO download required.

# Configuration guide

This project uses layered configuration so operators can keep safe defaults in
code, ship example YAML, and override sensitive or machine-specific values
locally. Cross-platform setup (Windows / macOS / Linux) always starts from
`uv sync --locked --all-groups` after cloning; see the root README quick start.

## Precedence

Highest priority wins:

1. **Application defaults** defined on the Pydantic settings models
2. **YAML file** passed to `load_settings(path)` (for example `configs/app.example.yaml`)
3. **Environment variables** with the `SMART_PARKING_` prefix
4. **Runtime overrides** dictionary (CLI / programmatic)

Example:

```python
from pathlib import Path

from smart_parking.config import load_parking_map, load_settings

settings = load_settings(
    Path("configs/app.example.yaml"),
    overrides={"api": {"port": 8080}},
)
parking_map = load_parking_map(settings.geometry.parking_map)
```

## Example files

| File | Purpose |
| --- | --- |
| `configs/app.example.yaml` | Full application settings matching SETUP.md |
| `configs/parking_spaces.example.json` | Sample three-bay parking map |
| `.env.example` | Environment variable names only (no secrets) |

Copy examples locally when needed. Do not commit real `.env` files, RTSP
credentials, footage, model weights, or SQLite databases.

## Environment variables

Common aliases:

| Variable | Maps to |
| --- | --- |
| `SMART_PARKING_LOG_LEVEL` | `app.log_level` |
| `SMART_PARKING_ENVIRONMENT` | `app.environment` |
| `SMART_PARKING_CAMERA_ID` | `camera.id` |
| `SMART_PARKING_CAMERA_SOURCE` | `camera.source` |
| `SMART_PARKING_DATABASE_URL` | `persistence.database_url` |
| `SMART_PARKING_MODEL_NAME` | `model.name` |
| `SMART_PARKING_MODEL_DEVICE` | `model.device` |
| `SMART_PARKING_MODEL_CONFIDENCE` | `model.confidence` |
| `SMART_PARKING_PARKING_MAP` | `geometry.parking_map` |
| `SMART_PARKING_API_HOST` | `api.host` |
| `SMART_PARKING_API_PORT` | `api.port` |

Nested overrides also work with double underscores, for example
`SMART_PARKING_MODEL__CONFIDENCE=0.4`.

## Secret handling

- Keep RTSP usernames and passwords in local `.env` or the process environment.
- Never put credentials in committed YAML.
- Prefer `SMART_PARKING_CAMERA_SOURCE` with credentials injected at runtime.
- Logs and error messages must not print raw RTSP URLs with embedded passwords
  (redaction lands with the pipeline/logging work).
- GitHub Actions secrets are reserved for release/deploy workflows that need them.

## Parking map validation

`load_parking_map` rejects maps that would break occupancy scoring:

- fewer than three polygon vertices
- non-positive polygon area (collinear / degenerate points)
- duplicate space IDs
- vertices outside the declared reference resolution

Validation errors include the space id and an actionable fix hint.

## Domain models

Domain types under `smart_parking.domain` describe boxes, detections, spaces,
occupancy states, snapshots, and events. They have no OpenCV or Ultralytics
imports so later adapters can change without rewriting core logic.

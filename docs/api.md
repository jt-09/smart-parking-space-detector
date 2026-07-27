# API and dashboard

Local FastAPI status API and lightweight Jinja2 dashboard for Smart Parking-Space Detector.

## Run locally

```bash
uv sync --locked --all-groups
uv run smart-parking serve --config configs/app.example.yaml
```

Defaults (from `settings.api`):

- Host: `127.0.0.1` (localhost only)
- Port: `8000`
- Dashboard: <http://127.0.0.1:8000/>
- OpenAPI UI: <http://127.0.0.1:8000/docs>
- OpenAPI JSON: <http://127.0.0.1:8000/openapi.json>

Overrides:

```bash
uv run smart-parking serve --config configs/app.example.yaml --host 127.0.0.1 --port 8000
uv run smart-parking serve --config configs/app.example.yaml --database-url sqlite:///output/parking.db
```

`--database-url` enables the SQLite repository for events, analytics, and runs endpoints.

## Operating modes

The API binds status from an injectable in-memory snapshot store.

1. **Separate-process (default for `serve`)** — `smart-parking process --persist` writes events/snapshots to SQLite; `serve` with persistence enabled serves historical analytics from that database. Live dashboard counts stay stale until a snapshot is injected (same-process or future shared store).
2. **Injected / test mode** — `create_app(..., snapshot=..., repository=...)` supplies fake state without a camera or YOLO weights (used by `TestClient` tests).

## Endpoints

Versioned under `/api/v1` (health is also available at `/health`).

| Method | Path | Description |
| --- | --- | --- |
| GET | `/health` | Liveness (`status`, `version`) |
| GET | `/api/v1/health` | Same liveness probe |
| GET | `/api/v1/status` | Counts, occupancy %, spaces, source freshness |
| GET | `/api/v1/spaces` | All spaces from the latest snapshot |
| GET | `/api/v1/spaces/{space_id}` | One space (`404` if missing) |
| GET | `/api/v1/events` | Persisted events (`space_id`, `run_id`, `after`, `before`, `limit`) |
| GET | `/api/v1/analytics/occupancy` | Hourly buckets + mean duration |
| GET | `/api/v1/analytics/turnover` | Occupied / vacated / unknown counts |
| GET | `/api/v1/runs` | Recent processing runs |
| GET | `/api/v1/runs/{run_id}` | One run (`404` if missing) |
| GET | `/` | Lightweight HTML dashboard |

Events / analytics / runs return **503** when persistence is not configured.

Invalid query parameters (for example `limit=0` or a non-ISO `after`) return **422** with a structured FastAPI error body containing `detail`.

## Example requests

```bash
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/api/v1/status
curl -s "http://127.0.0.1:8000/api/v1/spaces/A1"
curl -s "http://127.0.0.1:8000/api/v1/events?limit=20"
curl -s "http://127.0.0.1:8000/api/v1/analytics/occupancy?space_id=A2"
curl -s "http://127.0.0.1:8000/api/v1/analytics/turnover"
curl -s "http://127.0.0.1:8000/api/v1/runs"
```

Example status payload shape:

```json
{
  "camera_id": "lot-a-camera-01",
  "captured_at": "2026-07-27T12:00:00+00:00",
  "total_spaces": 4,
  "available": 1,
  "occupied": 1,
  "unknown": 2,
  "occupancy_percent": 50.0,
  "stale": true,
  "source": {
    "camera_id": "lot-a-camera-01",
    "source": "data/sample.mp4",
    "model_name": "yolo26n.pt",
    "model_device": "cpu",
    "last_frame_at": "2026-07-27T12:00:00+00:00",
    "stale": true,
    "max_frame_age_seconds": 3.0,
    "persistence_enabled": false
  },
  "spaces": []
}
```

## Dashboard

The `/` page shows:

- total / available / occupied / unknown counts and occupancy %
- per-space table with state, confidence, and unknown/pending flags
- latest events (when a repository is attached)
- source path, model name/device, last frame timestamp, and a clear **STALE** banner when the latest frame exceeds `camera.max_frame_age_seconds` or no snapshot exists

## Programmatic factory

```python
from fastapi.testclient import TestClient
from smart_parking.api import create_app
from smart_parking.config.models import Settings

app = create_app(settings=Settings(), snapshot=my_snapshot, repository=my_repo)
client = TestClient(app)
assert client.get("/api/v1/status").status_code == 200
```

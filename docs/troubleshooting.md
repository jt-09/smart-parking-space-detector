# Troubleshooting

Common failure modes for Smart Parking-Space Detector and how to resolve them.

## Installation and environment

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `uv: command not found` | `uv` not on `PATH` | Install via [astral.sh/uv](https://docs.astral.sh/uv/) and reopen the shell |
| Wrong Python version | System Python ≠ 3.11 | `uv python install 3.11` then `uv sync --locked --all-groups` |
| Import errors after pull | Lockfile / env drift | `uv sync --locked --all-groups` from the repo root |
| `ModuleNotFoundError: smart_parking` | Package not installed editable | Re-run `uv sync`; use `uv run …` rather than a bare `python` |

## OpenCV

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `cv2` import fails | Missing OpenCV wheel | `uv sync --locked --all-groups` |
| GUI editor window never appears | Headless / remote session | Run `edit-spaces` on a desktop session, or edit the parking-map JSON directly |
| Both `opencv-python` and `opencv-python-headless` installed | Conflicting wheels | Uninstall one. Local GUI: keep `opencv-python`. Containers: use headless only (see Dockerfile) |
| Codec / VideoWriter errors on Windows | Backend / fourcc mismatch | Prefer synthetic demos for CI; for real files try another codec or re-encode with ffmpeg |

## Models and YOLO

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| First YOLO run downloads weights slowly | Cold Ultralytics cache | Expected once; weights stay under the Ultralytics cache and must **not** be committed |
| Tests try to download models | Wrong detector backend | Use `--detector fake` / model name `fake` for weight-free runs |
| CUDA / device errors | GPU drivers or wrong `model.device` | Set `model.device: cpu` in config or `SMART_PARKING_MODEL_DEVICE=cpu` |
| Low occupancy accuracy on real footage | Thresholds / map mismatch | Recalibrate geometry thresholds and redraw polygons against a reference frame |

## Camera, RTSP, and codecs

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| RTSP reconnect loops | Network / auth / URL | Confirm the URL outside the app; put credentials in `.env` only |
| Credentials appear in logs | Misconfigured logging | Use the built-in redaction helpers; never log raw RTSP URIs with passwords |
| Webcam index fails (`0`, `1`) | Device busy or missing | Close other capture apps; try another index |
| EOF immediately on a file source | Bad path or empty media | Check `camera.source`; use `synthetic` for a deterministic short run |

## Pipeline and persistence

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Flickering occupancy | Confirmation too low | Raise `state.enter_confirm_frames` / `exit_confirm_frames` |
| Spaces stuck `unknown` | Invalid map or no overlap | Validate polygons; lower `candidate_score_threshold` carefully |
| SQLite locked / permission errors | Concurrent writers or read-only dir | One writer process; ensure `output/` is writable |
| Annotated video missing | `save_annotated_video: false` | Enable in config or pass `--save-video` |

## API and dashboard

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Cannot reach API from another host | Default bind is localhost | Bind `0.0.0.0` only inside trusted networks / containers |
| `/api/v1/events` returns 503 | Persistence disabled | Pass `--database-url` to `serve` or enable persistence in config |
| Stale dashboard counts | Separate process mode | Snapshot store is in-memory unless injected; run process with `--persist` and point `serve` at the same DB for history |

## Docker

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Image build fails locally | Docker daemon unavailable | Rely on GitHub Actions `build` job / a host with Docker; Dockerfile remains the source of truth |
| Container exits immediately | Bad CMD / missing entrypoint | Use the image default (`serve`) or `docker run … process --detector fake --source synthetic` |
| Health check failing | API not listening yet | Wait for `start-period`; confirm `/health` on the published port |
| Permission errors writing output | Volume ownership | Mount a writable volume at `/app/output`; image runs as UID 10001 |

## CI and quality gates

```bash
uv sync --locked --all-groups
uv run ruff format .
uv run ruff check .
uv run mypy src
uv run pytest --cov=smart_parking --cov-fail-under=85
uv run python scripts/smoke_test.py
```

Required branch checks on `main`: `quality`, `unit-tests`, `integration-tests`, `build`.

## Still stuck?

1. Re-run `uv run python scripts/smoke_test.py` and capture the first failing step.
2. Confirm you did not commit `.env`, weights (`*.pt`), footage, or SQLite databases.
3. Open an issue with OS, `uv --version`, and the failing command output (redact secrets).

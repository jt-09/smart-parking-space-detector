# Vehicle detection

Smart Parking detects vehicles through a backend-agnostic `Detector` protocol.
Domain and pipeline code consume `Detection` / `DetectionBatch` objects only —
never Ultralytics types.

## Architecture

| Component | Role |
| --- | --- |
| `smart_parking.detection.base.Detector` | Protocol: `detect(image) -> DetectionBatch` |
| `smart_parking.detection.models.DetectionBatch` | Normalized frame result + provenance |
| `smart_parking.domain.parking.Detection` | Per-vehicle box, class, confidence, optional `track_id` |
| `UltralyticsDetector` | YOLO adapter (configurable model/device/thresholds) |
| `FakeDetector` | Deterministic boxes for tests (no network or weights) |

Default vehicle classes: `car`, `motorcycle`, `bus`, `truck`.

## Models and devices

Configuration lives under `model` in application settings (see
[`configuration.md`](configuration.md)):

| Setting | Default | Notes |
| --- | --- | --- |
| `model.name` | `yolo26n.pt` | Ultralytics model name or local path |
| `model.device` | `cpu` | CPU is the supported default; GPU is optional |
| `model.confidence` | `0.30` | Minimum detection score |
| `model.iou` | `0.50` | NMS IoU threshold |
| `model.allowed_classes` | car / motorcycle / bus / truck | Case-insensitive names |
| `model.tracking_enabled` | `true` | Uses Ultralytics `track` when enabled |
| `model.tracker` | unset | Optional tracker config name/path |

Logs emit the selected model and device when the adapter loads weights.

```python
from smart_parking.detection import FakeDetector, UltralyticsDetector, default_fake_detections

# Tests / CI — always safe
fake = FakeDetector(default_fake_detections())
batch = fake.detect(image_bgr)

# Local / demo — downloads weights on first use if missing
detector = UltralyticsDetector(model_name="yolo26n.pt", device="cpu")
batch = detector.detect(image_bgr, frame_index=0)
```

## Model download behaviour

- Weights are **not** committed. `.gitignore` ignores `*.pt`, `*.onnx`, `*.engine`, and related artifacts.
- The first call that constructs `YOLO(model_name)` may download pretrained weights into the working directory or Ultralytics cache when the file is absent and the network is available.
- **Unit and CI tests must not require a download.** `FakeDetector` contract tests always run. The Ultralytics CPU smoke test runs only when:
  - `ULTRALYTICS_SMOKE=1`, and
  - a local weight file exists (`yolo26n.pt` or `yolov8n.pt`).

```powershell
# Optional local smoke (after manually placing or downloading weights)
$env:ULTRALYTICS_SMOKE = "1"
uv run pytest tests/unit/test_detection.py -k ultralytics_adapter_cpu_smoke
```

## Tracking

When `tracking_enabled` is true, the adapter calls Ultralytics `model.track(..., persist=True)` and maps each box id to `Detection.track_id` (string). Occupancy and event attribution can use these persistent identifiers without depending on Ultralytics.

## Licensing

This project is **AGPL-3.0**. Ultralytics YOLO is also AGPL-3.0 for typical open-source use. Closed-source or commercial redistribution needs independent licensing review of both this repository and Ultralytics. This is not legal advice. See the root `LICENSE` and Ultralytics documentation:

- https://docs.ultralytics.com/
- https://docs.ultralytics.com/models/yolo26/
- https://docs.ultralytics.com/modes/track/

## Troubleshooting

| Symptom | Likely cause | Mitigation |
| --- | --- | --- |
| CI fails downloading weights | Smoke test not gated | Keep `ULTRALYTICS_SMOKE` unset in CI; use `FakeDetector` |
| `ModuleNotFoundError: ultralytics` | Incomplete sync | `uv sync --locked --all-groups` |
| Empty detections on real video | Confidence / class filter | Lower `model.confidence`; confirm `allowed_classes` |
| GPU OOM | Device set to CUDA | Set `model.device: cpu` or a smaller nano model |
| Track IDs always `None` | Tracking disabled or predict path | Enable `model.tracking_enabled` |
| Accidental weight commit | `.pt` not ignored | Confirm `*.pt` in `.gitignore`; never `git add` weights |

## Related docs

- [`configuration.md`](configuration.md) — settings precedence and `model.*` fields
- [`development-timeline.md`](development-timeline.md) — PR commit proposals

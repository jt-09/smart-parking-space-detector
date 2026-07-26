# Processing pipeline

End-to-end occupancy processing wires existing modules without duplicating
business logic in the CLI or renderer.

## Stages

1. **Frame source** — OpenCV video/camera/stream or `synthetic` token
2. **Sampling** — `video.process_every_n_frames` keeps every Nth frame
3. **Detector** — protocol adapter (`UltralyticsDetector` or `FakeDetector`)
4. **Geometry** — scale map to frame, score overlaps, greedy one-to-one assignment
5. **Occupancy engine** — hysteresis + temporal confirmation → confirmed states
6. **Renderer** — draw polygons, labels, detections, counts, FPS (drawing only)
7. **Writers** — annotated MP4 + JSONL snapshots under `app.output_dir`

## CLI

```bash
uv run smart-parking process \
  --config configs/app.example.yaml \
  --source path/to/clip.mp4 \
  --parking-map configs/parking_spaces.example.json \
  --output-dir output/run1
```

Weight-free dry run:

```bash
uv run smart-parking process \
  --source synthetic:64:48:30 \
  --detector fake \
  --parking-map configs/parking_spaces.example.json \
  --output-dir output/synth \
  --no-save-video
```

Ctrl+C requests a graceful stop after the current frame. Capture and writers
are always closed in a `finally` block so a failed video writer cannot leak
the frame source.

## Outputs

| Artifact | Name pattern |
| --- | --- |
| Annotated video | `annotated_<run_id>.mp4` |
| Snapshots | `snapshots_<run_id>.jsonl` |
| Metrics | `metrics_<run_id>.json` |

JSONL rows use **confirmed** occupancy state from the engine, not raw detector
scores. Generated media stays under `output/` (gitignored) and must not be
committed.

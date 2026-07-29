# Evaluation and performance benchmarks

Repeatable occupancy accuracy metrics and pipeline throughput measurement for
Smart Parking-Space Detector.

## Scope and honesty

- The **default** throughput path uses `SyntheticFrameSource` + `FakeDetector`.
  It does **not** download YOLO weights and is deterministic for CI.
- Accuracy numbers on synthetic demos are **not** claims about real parking-lot
  footage. Do not invent or imply real-footage acceptance (for example “90%+ on
  site video”) without a separately licensed, documented evaluation set.
- When real footage is evaluated later, record camera, model, thresholds,
  hardware, and the exact clip — and label results as specific to that setup.

## Ground-truth format

CSV or JSON with columns / keys:

| Field | Meaning |
| --- | --- |
| `frame_or_time` | Frame index or timestamp used for alignment |
| `space_id` | Parking-space identifier |
| `expected_state` | `available`, `occupied`, or `unknown` |

Example CSV (also under [`assets/evaluation_ground_truth.example.csv`](assets/evaluation_ground_truth.example.csv)):

```text
frame_or_time,space_id,expected_state
0.0,A-001,available
3.2,A-001,occupied
18.7,A-001,available
```

JSON may be a bare array or `{"labels": [...]}`.

Predictions use the same shape with `predicted_state` (or `expected_state` as an
alias). See [`assets/evaluation_predictions.example.csv`](assets/evaluation_predictions.example.csv).

## Metrics

Computed by `smart_parking.evaluation.metrics.evaluate_occupancy`:

| Metric | Description |
| --- | --- |
| Per-space accuracy | Correct / total matched labels for each `space_id` |
| Macro accuracy | Unweighted mean of per-space accuracies |
| Occupied precision / recall / F1 | Binary metrics treating `occupied` as the positive class |
| Transition precision / recall | Matched confirmed state changes (`available`↔`occupied`) |
| False flips | Unmatched predicted transitions (spurious flips) |
| Mean / p95 transition latency | `predicted_at − ground_truth_at` for matched transitions |

Pending engine states (`pending_occupied`, `pending_available`) collapse toward
their intended confirmed label for scoring.

## Throughput benchmark

Measures:

- decode FPS (frames read / wall time)
- inference FPS (from reported / injected inference timing)
- end-to-end FPS (frames processed / wall time)
- peak resident memory (best-effort; Windows peak working set or `ru_maxrss`)
- hardware / Python / config summary for the report header

### Commands

```bash
# Preferred operator entrypoint
uv run smart-parking benchmark --frames 60 --report docs/assets/benchmark_report.txt

# Script equivalent
uv run python scripts/benchmark.py --frames 60 -o docs/assets/benchmark_report.txt

# Optional occupancy scoring against files
uv run smart-parking benchmark \
  --ground-truth docs/assets/evaluation_ground_truth.example.csv \
  --predictions docs/assets/evaluation_predictions.example.csv \
  --report docs/assets/benchmark_report.txt
```

Generated reports are plain text only. Do not commit large binaries, weights,
databases, or annotated videos.

## Report template

A typical report includes:

1. generation timestamp (UTC)
2. scope note (synthetic vs any future real clip)
3. throughput block (FPS, peak RSS, frame size, detector, device)
4. hardware block (OS, machine, processor, Python, CPU count)
5. config block (frame count, sampling, injected inference delay)
6. optional occupancy block (macro / per-space / occupied / transitions)

Write output with `--report` / `-o`. Example committed template text may live
under `docs/assets/` after a local run; regenerate rather than hand-editing
hardware lines.

## Acceptance targets

| Target | Status on default synthetic + FakeDetector path |
| --- | --- |
| Metric math correctness | Covered by unit tests on known toy examples |
| Repeatable throughput + memory | Available via CLI / `scripts/benchmark.py` |
| ≥90% occupancy on real footage | **Not claimed** — no licensed real-footage set in-repo |
| README performance claims | Must link here and name hardware / config |

Tune hysteresis and overlap thresholds for demos carefully. Prefer documenting
limitations over overfitting a single synthetic clip.

## Library API

```python
from smart_parking.evaluation import (
    evaluate_occupancy,
    load_ground_truth,
    load_predictions,
    run_throughput_benchmark,
    format_benchmark_report,
)

throughput = run_throughput_benchmark(frame_count=60)
report = evaluate_occupancy(
    load_ground_truth("docs/assets/evaluation_ground_truth.example.csv"),
    load_predictions("docs/assets/evaluation_predictions.example.csv"),
)
print(format_benchmark_report(throughput=throughput, occupancy=report))
```

## Example synthetic throughput (committed template)

See [`assets/benchmark_report.example.txt`](assets/benchmark_report.example.txt)
for a reproducible FakeDetector sample (≈408 e2e FPS / ≈72 MiB RSS on one
Windows AMD64 host, 60×320×240 frames). Numbers vary by machine; regenerate
locally and cite hardware when quoting results.

## Related docs

- [`pipeline.md`](pipeline.md) — processing loop and FPS counters
- [`detection.md`](detection.md) — FakeDetector vs Ultralytics
- [`dataset-and-privacy.md`](dataset-and-privacy.md) — media policy
- [`SETUP.md`](../SETUP.md) §13 — evaluation requirements

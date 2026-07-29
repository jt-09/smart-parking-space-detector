#!/usr/bin/env python3
"""CLI-friendly throughput benchmark entrypoint (no YOLO download).

Examples::

    uv run python scripts/benchmark.py
    uv run python scripts/benchmark.py --frames 90 --report docs/assets/benchmark_report.txt
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run Smart Parking synthetic FakeDetector throughput benchmarks "
            "and optionally score occupancy predictions against ground truth."
        )
    )
    parser.add_argument("--frames", type=int, default=60, help="Synthetic frame count.")
    parser.add_argument("--width", type=int, default=320, help="Frame width.")
    parser.add_argument("--height", type=int, default=240, help="Frame height.")
    parser.add_argument(
        "--report",
        "-o",
        type=Path,
        default=None,
        help="Optional plain-text report output path.",
    )
    parser.add_argument(
        "--ground-truth",
        "-g",
        type=Path,
        default=None,
        help="Optional ground-truth CSV/JSON.",
    )
    parser.add_argument(
        "--predictions",
        "-p",
        type=Path,
        default=None,
        help="Optional predictions CSV/JSON (required with --ground-truth).",
    )
    parser.add_argument(
        "--match-tolerance",
        type=float,
        default=0.0,
        help="Max |frame_or_time| delta when pairing labels.",
    )
    args = parser.parse_args(argv)

    from smart_parking.evaluation.ground_truth import load_ground_truth
    from smart_parking.evaluation.metrics import evaluate_occupancy
    from smart_parking.evaluation.predictions import load_predictions
    from smart_parking.evaluation.report import format_benchmark_report, write_benchmark_report
    from smart_parking.evaluation.throughput import run_throughput_benchmark

    try:
        throughput = run_throughput_benchmark(
            frame_count=args.frames,
            width=args.width,
            height=args.height,
        )
        occupancy = None
        if args.ground_truth is not None:
            if args.predictions is None:
                print(
                    "error: --predictions is required when --ground-truth is set",
                    file=sys.stderr,
                )
                return 1
            occupancy = evaluate_occupancy(
                load_ground_truth(args.ground_truth),
                load_predictions(args.predictions),
                match_tolerance=args.match_tolerance,
            )
        text = format_benchmark_report(
            throughput=throughput,
            occupancy=occupancy,
            notes=[
                "Default throughput path uses FakeDetector (no YOLO download).",
                "Synthetic accuracy is not a real-footage acceptance claim.",
            ],
        )
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(text, end="")
    if args.report is not None:
        dest = write_benchmark_report(args.report, text)
        print(f"Report written to {dest}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

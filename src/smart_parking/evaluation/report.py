"""Plain-text evaluation and benchmark report formatting."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from smart_parking.evaluation.metrics import OccupancyEvaluationReport
from smart_parking.evaluation.throughput import ThroughputResult


def _fmt_float(value: float | None, digits: int = 4) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}"


def format_occupancy_section(report: OccupancyEvaluationReport) -> str:
    """Render occupancy accuracy metrics as plain text."""
    lines = [
        "Occupancy accuracy",
        "------------------",
        f"samples: {report.sample_count}  matched: {report.matched_count}",
        f"macro_accuracy: {_fmt_float(report.macro_accuracy)}",
        "per_space_accuracy:",
    ]
    if report.per_space_accuracy:
        for space_id, value in sorted(report.per_space_accuracy.items()):
            lines.append(f"  {space_id}: {_fmt_float(value)}")
    else:
        lines.append("  (none)")
    occ = report.occupied
    lines.extend(
        [
            "occupied class:",
            f"  precision: {_fmt_float(occ.precision)}",
            f"  recall:    {_fmt_float(occ.recall)}",
            f"  f1:        {_fmt_float(occ.f1)}",
            (
                f"  tp={occ.true_positives} fp={occ.false_positives} "
                f"fn={occ.false_negatives} tn={occ.true_negatives}"
            ),
        ]
    )
    tr = report.transitions
    lines.extend(
        [
            "transitions:",
            f"  precision: {_fmt_float(tr.precision)}",
            f"  recall:    {_fmt_float(tr.recall)}",
            f"  false_flips: {tr.false_flips}",
            f"  mean_latency: {_fmt_float(tr.mean_latency)}",
            f"  p95_latency:  {_fmt_float(tr.p95_latency)}",
        ]
    )
    return "\n".join(lines)


def format_throughput_section(result: ThroughputResult) -> str:
    """Render throughput and hardware metadata as plain text."""
    hw = result.hardware
    peak_mib = (
        f"{result.peak_rss_bytes / (1024.0 * 1024.0):.2f} MiB"
        if result.peak_rss_bytes is not None
        else "n/a"
    )
    lines = [
        "Throughput",
        "----------",
        f"frames_read: {result.frames_read}  frames_processed: {result.frames_processed}",
        f"decode_fps: {_fmt_float(result.decode_fps, 2)}",
        f"inference_fps: {_fmt_float(result.inference_fps, 2)}",
        f"e2e_fps: {_fmt_float(result.e2e_fps, 2)}",
        f"elapsed_seconds: {_fmt_float(result.elapsed_seconds, 3)}",
        f"peak_rss: {peak_mib}",
        f"frame_size: {result.width}x{result.height}",
        f"detector: {result.detector}  device: {result.device}",
        "hardware:",
        f"  system: {hw.system} {hw.release} ({hw.machine})",
        f"  processor: {hw.processor}",
        f"  python: {hw.python_version}  cpu_count: {hw.cpu_count}",
        "config:",
    ]
    for key, value in sorted(result.config_summary.items()):
        lines.append(f"  {key}: {value}")
    return "\n".join(lines)


def format_benchmark_report(
    *,
    throughput: ThroughputResult | None = None,
    occupancy: OccupancyEvaluationReport | None = None,
    notes: list[str] | None = None,
    generated_at: datetime | None = None,
) -> str:
    """Build a complete plain-text evaluation / benchmark report."""
    moment = generated_at or datetime.now(UTC)
    header = [
        "Smart Parking - evaluation / benchmark report",
        f"generated_at_utc: {moment.astimezone(UTC).isoformat().replace('+00:00', 'Z')}",
        "",
        "Scope note: default throughput uses SyntheticFrameSource + FakeDetector.",
        "Do not extrapolate synthetic-demo accuracy to unlicensed real footage.",
        "",
    ]
    body: list[str] = []
    if throughput is not None:
        body.append(format_throughput_section(throughput))
        body.append("")
    if occupancy is not None:
        body.append(format_occupancy_section(occupancy))
        body.append("")
    if notes:
        body.append("Notes")
        body.append("-----")
        body.extend(f"- {note}" for note in notes)
        body.append("")
    return "\n".join(header + body).rstrip() + "\n"


def write_benchmark_report(path: Path | str, text: str) -> Path:
    """Write a report to disk (text only; no large binaries)."""
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    return dest


def report_to_dict(
    *,
    throughput: ThroughputResult | None = None,
    occupancy: OccupancyEvaluationReport | None = None,
) -> dict[str, Any]:
    """Machine-readable companion payload for the text report."""
    payload: dict[str, Any] = {}
    if throughput is not None:
        payload["throughput"] = throughput.as_dict()
    if occupancy is not None:
        payload["occupancy"] = occupancy.as_dict()
    return payload

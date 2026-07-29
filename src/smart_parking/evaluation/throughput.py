"""Pipeline throughput and peak-memory measurement (synthetic + FakeDetector)."""

from __future__ import annotations

import platform
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from smart_parking.config.models import (
    AppSettings,
    CameraSettings,
    GeometrySettings,
    ModelSettings,
    Settings,
    StateSettings,
    VideoSettings,
)
from smart_parking.detection.fake import FakeDetector
from smart_parking.detection.models import BoundingBox, Detection
from smart_parking.domain.parking import ParkingMap, ParkingSpace, Point
from smart_parking.pipeline.processor import ParkingProcessor
from smart_parking.sources.synthetic import SyntheticFrameSource


@dataclass(frozen=True, slots=True)
class HardwareInfo:
    """Host metadata recorded alongside a benchmark run."""

    system: str
    release: str
    machine: str
    processor: str
    python_version: str
    cpu_count: int | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ThroughputResult:
    """Decode / inference / end-to-end throughput plus peak memory."""

    frames_read: int
    frames_processed: int
    decode_fps: float
    inference_fps: float
    e2e_fps: float
    elapsed_seconds: float
    peak_rss_bytes: int | None
    width: int
    height: int
    detector: str
    device: str
    hardware: HardwareInfo
    config_summary: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["hardware"] = self.hardware.as_dict()
        if self.peak_rss_bytes is not None:
            payload["peak_rss_mib"] = self.peak_rss_bytes / (1024.0 * 1024.0)
        else:
            payload["peak_rss_mib"] = None
        return payload


def collect_hardware_info() -> HardwareInfo:
    """Capture portable host metadata for the evaluation report."""
    cpu_count: int | None
    try:
        import os

        cpu_count = os.cpu_count()
    except Exception:  # pragma: no cover - extremely defensive
        cpu_count = None
    return HardwareInfo(
        system=platform.system(),
        release=platform.release(),
        machine=platform.machine(),
        processor=platform.processor() or "unknown",
        python_version=platform.python_version(),
        cpu_count=cpu_count,
    )


def current_rss_bytes() -> int | None:
    """Best-effort current resident set size without optional dependencies."""
    if sys.platform == "win32":
        return _windows_rss_bytes()
    try:
        import resource

        usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # Linux: kilobytes; macOS: bytes.
        if sys.platform == "darwin":
            return int(usage)
        return int(usage) * 1024
    except Exception:
        return None


def _windows_rss_bytes() -> int | None:
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
        # WinDLL avoids ctypes.windll attribute access that fails under mypy on Linux.
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        get_mem = psapi.GetProcessMemoryInfo
        get_mem.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
            wintypes.DWORD,
        ]
        get_mem.restype = wintypes.BOOL
        ok = get_mem(kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb)
        if not ok:
            return None
        return int(counters.PeakWorkingSetSize)
    except Exception:
        return None


def _parking_map(width: int, height: int) -> ParkingMap:
    mid = width // 2

    def bay(space_id: str, x1: float, x2: float) -> ParkingSpace:
        return ParkingSpace(
            id=space_id,
            label=space_id,
            polygon=(
                Point(x1, height * 0.15),
                Point(x2, height * 0.15),
                Point(x2, height * 0.9),
                Point(x1, height * 0.9),
            ),
        )

    return ParkingMap(
        camera_id="bench-cam",
        reference_width=width,
        reference_height=height,
        spaces=(
            bay("A1", width * 0.05, mid - width * 0.05),
            bay("A2", mid + width * 0.05, width * 0.95),
        ),
    )


def _fake_detector(width: int, height: int, *, inference_ms: float = 0.5) -> FakeDetector:
    # Box fully inside left bay so geometry/occupancy do real work.
    mid = width / 2.0
    detection = Detection(
        bbox=BoundingBox(
            x1=width * 0.08,
            y1=height * 0.2,
            x2=mid - width * 0.08,
            y2=height * 0.85,
        ),
        confidence=0.93,
        class_id=2,
        class_name="car",
        track_id="1",
    )
    return FakeDetector(
        (detection,),
        device="cpu",
        inference_ms=inference_ms,
    )


def run_throughput_benchmark(
    *,
    frame_count: int = 60,
    width: int = 320,
    height: int = 240,
    fps: float = 30.0,
    process_every_n_frames: int = 1,
    output_dir: Path | None = None,
    inference_ms: float = 0.5,
) -> ThroughputResult:
    """Run a deterministic FakeDetector + SyntheticFrameSource throughput trial.

    Does not download YOLO weights and does not write annotated video by default.
    """
    if frame_count < 1:
        raise ValueError(f"frame_count must be >= 1, got {frame_count}.")
    if width < 16 or height < 16:
        raise ValueError(f"frame size too small: {width}x{height}.")

    out = output_dir if output_dir is not None else Path("outputs") / "benchmark"
    settings = Settings(
        app=AppSettings(environment="test", output_dir=out),
        camera=CameraSettings(id="bench-cam", source="synthetic"),
        video=VideoSettings(
            process_every_n_frames=process_every_n_frames,
            save_annotated_video=False,
            output_fps=fps,
        ),
        model=ModelSettings(name="fake", device="cpu"),
        geometry=GeometrySettings(
            parking_map=Path("unused.json"),
            candidate_score_threshold=0.10,
            occupied_enter_threshold=0.25,
            occupied_exit_threshold=0.10,
        ),
        state=StateSettings(
            mode="frames",
            enter_confirm_frames=2,
            exit_confirm_frames=2,
            unknown_after_invalid_frames=10,
        ),
    )
    parking = _parking_map(width, height)
    source = SyntheticFrameSource(
        source_id="benchmark-synthetic",
        width=width,
        height=height,
        frame_count=frame_count,
        fps=fps,
        moving_rectangle=True,
    )
    detector = _fake_detector(width, height, inference_ms=inference_ms)
    processor = ParkingProcessor(settings, parking, source, detector)

    before_rss = current_rss_bytes()
    started = time.perf_counter()
    result = processor.run()
    elapsed = max(time.perf_counter() - started, 1e-9)
    after_rss = current_rss_bytes()
    peak = None
    if before_rss is not None or after_rss is not None:
        candidates = [v for v in (before_rss, after_rss) if v is not None]
        peak = max(candidates) if candidates else None
    # Prefer OS peak working set when available (Windows PeakWorkingSetSize).
    live_peak = current_rss_bytes()
    if live_peak is not None:
        peak = max(peak or 0, live_peak)

    metrics = result.metrics
    decode_fps = metrics.frames_read / elapsed
    e2e_fps = metrics.frames_processed / elapsed
    if metrics.last_inference_ms and metrics.last_inference_ms > 0:
        inference_fps = 1000.0 / metrics.last_inference_ms
    else:
        inference_fps = metrics.inference_fps

    return ThroughputResult(
        frames_read=metrics.frames_read,
        frames_processed=metrics.frames_processed,
        decode_fps=decode_fps,
        inference_fps=inference_fps,
        e2e_fps=e2e_fps,
        elapsed_seconds=elapsed,
        peak_rss_bytes=peak,
        width=width,
        height=height,
        detector="fake",
        device="cpu",
        hardware=collect_hardware_info(),
        config_summary={
            "frame_count": frame_count,
            "fps": fps,
            "process_every_n_frames": process_every_n_frames,
            "inference_ms_injected": inference_ms,
            "save_annotated_video": False,
            "model": "fake",
        },
    )

"""Annotated video and JSONL snapshot writers for pipeline output."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from smart_parking.domain.state import OccupancySnapshot
from smart_parking.pipeline.snapshot import PipelineMetrics, snapshot_to_dict

logger = logging.getLogger(__name__)

ImageArray = NDArray[np.uint8]


def ensure_output_dir(path: Path) -> Path:
    """Create ``path`` (and parents) safely; return the resolved directory."""
    path.mkdir(parents=True, exist_ok=True)
    return path


class AnnotatedVideoWriter:
    """Write annotated BGR frames to an MP4 (or other OpenCV FourCC) file."""

    def __init__(
        self,
        path: Path | str,
        *,
        fps: float = 10.0,
        frame_size: tuple[int, int] | None = None,
        fourcc: str = "mp4v",
    ) -> None:
        if fps <= 0:
            raise ValueError(f"fps must be > 0, got {fps}.")
        self._path = Path(path)
        self._fps = float(fps)
        self._frame_size = frame_size
        self._fourcc = fourcc
        self._writer: cv2.VideoWriter | None = None
        self._frames_written = 0
        ensure_output_dir(self._path.parent)

    @property
    def path(self) -> Path:
        return self._path

    @property
    def frames_written(self) -> int:
        return self._frames_written

    @property
    def is_open(self) -> bool:
        return self._writer is not None and self._writer.isOpened()

    def _open(self, width: int, height: int) -> None:
        ensure_output_dir(self._path.parent)
        fourcc_fn = getattr(cv2, "VideoWriter_fourcc", None)
        if fourcc_fn is None:  # pragma: no cover - OpenCV always provides this
            raise RuntimeError("OpenCV VideoWriter_fourcc is unavailable.")
        code = fourcc_fn(*self._fourcc)
        writer = cv2.VideoWriter(str(self._path), code, self._fps, (width, height))
        if not writer.isOpened():
            writer.release()
            msg = f"Failed to open annotated video writer at {self._path}."
            raise RuntimeError(msg)
        self._writer = writer
        self._frame_size = (width, height)

    def write(self, frame: ImageArray) -> None:
        if frame.ndim != 3 or frame.shape[2] != 3:
            raise ValueError(f"frame must be HxWx3 BGR, got shape {frame.shape}.")
        height, width = int(frame.shape[0]), int(frame.shape[1])
        if self._writer is None:
            self._open(width, height)
        assert self._writer is not None
        expected = self._frame_size
        if expected is None or expected != (width, height):
            msg = (
                f"Frame size {width}x{height} does not match writer "
                f"{expected[0] if expected else '?'}x{expected[1] if expected else '?'}."
            )
            raise ValueError(msg)
        self._writer.write(frame)
        self._frames_written += 1

    def __call__(
        self,
        annotated: ImageArray,
        snapshot: OccupancySnapshot,
        metrics: PipelineMetrics,
    ) -> None:
        del snapshot, metrics  # sink signature shared with processor
        self.write(annotated)

    def close(self) -> None:
        if self._writer is not None:
            self._writer.release()
            self._writer = None
            logger.debug(
                "Closed annotated video writer (%s frames) at %s",
                self._frames_written,
                self._path,
            )

    def __enter__(self) -> AnnotatedVideoWriter:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object,
    ) -> None:
        del exc_type, exc, tb
        self.close()


class JsonlSnapshotWriter:
    """Append occupancy snapshots as JSON Lines under the output directory."""

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        ensure_output_dir(self._path.parent)
        self._handle = self._path.open("w", encoding="utf-8")
        self._rows_written = 0

    @property
    def path(self) -> Path:
        return self._path

    @property
    def rows_written(self) -> int:
        return self._rows_written

    def write(self, snapshot: OccupancySnapshot, metrics: PipelineMetrics | None = None) -> None:
        payload = snapshot_to_dict(snapshot, metrics=metrics)
        self._handle.write(json.dumps(payload, separators=(",", ":"), default=str))
        self._handle.write("\n")
        self._handle.flush()
        self._rows_written += 1

    def __call__(self, snapshot: OccupancySnapshot, metrics: PipelineMetrics) -> None:
        self.write(snapshot, metrics)

    def close(self) -> None:
        if not self._handle.closed:
            self._handle.close()
            logger.debug(
                "Closed JSONL snapshot writer (%s rows) at %s",
                self._rows_written,
                self._path,
            )

    def __enter__(self) -> JsonlSnapshotWriter:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object,
    ) -> None:
        del exc_type, exc, tb
        self.close()


def build_output_paths(output_dir: Path | str, *, run_id: str) -> dict[str, Path]:
    """Standard artifact paths for a processing run."""
    root = ensure_output_dir(Path(output_dir))
    return {
        "dir": root,
        "annotated_video": root / f"annotated_{run_id}.mp4",
        "snapshots_jsonl": root / f"snapshots_{run_id}.jsonl",
        "metrics_json": root / f"metrics_{run_id}.json",
    }


def write_metrics_json(path: Path, metrics: PipelineMetrics, **extra: Any) -> None:
    """Persist final run metrics as JSON."""
    ensure_output_dir(path.parent)
    payload = metrics.as_dict()
    payload.update(extra)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

"""Deterministic synthetic frame source for tests and demos."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Self

import numpy as np

from smart_parking.sources.base import (
    Frame,
    FrameMetadata,
    FrameSourceClosed,
    ImageArray,
)


class SyntheticFrameSource:
    """Generate deterministic coloured frames without OpenCV or real media.

    Optional moving rectangle simulates a vehicle footprint for pipeline tests.
    """

    def __init__(
        self,
        *,
        source_id: str = "synthetic",
        width: int = 64,
        height: int = 48,
        frame_count: int = 10,
        fps: float = 10.0,
        start_time: datetime | None = None,
        moving_rectangle: bool = False,
    ) -> None:
        if width <= 0 or height <= 0:
            raise ValueError(f"dimensions must be positive, got {width}x{height}.")
        if frame_count < 0:
            raise ValueError(f"frame_count must be >= 0, got {frame_count}.")
        if fps <= 0.0:
            raise ValueError(f"fps must be > 0, got {fps}.")
        if not source_id.strip():
            raise ValueError("source_id must be a non-empty string.")

        self._source_id = source_id
        self._width = width
        self._height = height
        self._frame_count = frame_count
        self._fps = fps
        self._start_time = start_time or datetime(2026, 7, 23, 15, 0, 0, tzinfo=UTC)
        if self._start_time.tzinfo is None:
            raise ValueError("start_time must be timezone-aware (UTC expected).")
        self._moving_rectangle = moving_rectangle
        self._index = 0
        self._opened = False
        self._closed = False

    @property
    def source_id(self) -> str:
        return self._source_id

    @property
    def is_open(self) -> bool:
        return self._opened and not self._closed

    def open(self) -> None:
        if self._closed:
            raise FrameSourceClosed("SyntheticFrameSource was already closed.")
        self._opened = True
        self._index = 0

    def close(self) -> None:
        self._opened = False
        self._closed = True

    def read(self) -> Frame | None:
        if self._closed:
            raise FrameSourceClosed("Cannot read from a closed SyntheticFrameSource.")
        if not self._opened:
            raise FrameSourceClosed("SyntheticFrameSource is not open; call open() first.")
        if self._index >= self._frame_count:
            return None

        image = self._render_frame(self._index)
        timestamp = self._start_time + timedelta(seconds=self._index / self._fps)
        metadata = FrameMetadata(
            timestamp=timestamp,
            index=self._index,
            source_id=self._source_id,
            width=self._width,
            height=self._height,
        )
        frame = Frame(image=image, metadata=metadata)
        self._index += 1
        return frame

    def __iter__(self) -> Iterator[Frame]:
        self.open()
        try:
            while True:
                frame = self.read()
                if frame is None:
                    break
                yield frame
        finally:
            self.close()

    def __enter__(self) -> Self:
        self.open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object,
    ) -> None:
        self.close()

    def _render_frame(self, index: int) -> ImageArray:
        # Deterministic BGR colour from index (no random).
        b = (40 + index * 17) % 256
        g = (80 + index * 31) % 256
        r = (120 + index * 47) % 256
        image = np.full((self._height, self._width, 3), (b, g, r), dtype=np.uint8)

        if self._moving_rectangle:
            rect_w, rect_h = max(8, self._width // 8), max(6, self._height // 6)
            max_x = max(0, self._width - rect_w)
            x0 = (index * 3) % (max_x + 1) if max_x > 0 else 0
            y0 = self._height // 3
            x1, y1 = x0 + rect_w, y0 + rect_h
            image[y0:y1, x0:x1] = (0, 0, 255)  # red rectangle in BGR

        return image

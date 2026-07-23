"""OpenCV-backed frame source adapter for files, webcams, and streams."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Self, cast

import cv2
import numpy as np

from smart_parking.sources.base import (
    Frame,
    FrameMetadata,
    FrameSourceClosed,
    FrameSourceError,
    ImageArray,
    ReconnectPolicy,
    redact_source_uri,
)

logger = logging.getLogger(__name__)


def _is_stream_uri(source: str | int) -> bool:
    if isinstance(source, int):
        return False
    lowered = source.lower()
    return lowered.startswith(("rtsp://", "rtsps://", "http://", "https://", "tcp://"))


def _is_image_path(path: Path) -> bool:
    return path.suffix.lower() in {
        ".jpg",
        ".jpeg",
        ".png",
        ".bmp",
        ".tif",
        ".tiff",
        ".webp",
    }


class OpenCVFrameSource:
    """Capture frames via OpenCV ``VideoCapture`` / ``imread``.

    Domain and pipeline code should depend on :class:`~smart_parking.sources.base.FrameSource`
    rather than this concrete adapter so OpenCV types do not leak outward.
    """

    def __init__(
        self,
        source: str | int,
        *,
        source_id: str | None = None,
        reconnect: ReconnectPolicy | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self._raw_source = source
        self._source_id = source_id or _default_source_id(source)
        self._reconnect = reconnect or ReconnectPolicy()
        self._sleep = sleep or time.sleep
        self._capture: cv2.VideoCapture | None = None
        self._image_frame: ImageArray | None = None
        self._image_consumed = False
        self._index = 0
        self._opened = False
        self._closed = False
        self._is_stream = _is_stream_uri(source)
        self._is_image = False
        if isinstance(source, str) and not self._is_stream:
            path = Path(source)
            self._is_image = path.is_file() and _is_image_path(path)

    @property
    def source_id(self) -> str:
        return self._source_id

    @property
    def is_open(self) -> bool:
        return self._opened and not self._closed

    @property
    def safe_source_label(self) -> str:
        """Human-readable source label with credentials redacted."""
        if isinstance(self._raw_source, int):
            return f"camera:{self._raw_source}"
        return redact_source_uri(self._raw_source)

    def open(self) -> None:
        if self._closed:
            raise FrameSourceClosed("OpenCVFrameSource was already closed.")
        if self._opened:
            return
        self._open_capture()
        self._opened = True
        self._index = 0
        self._image_consumed = False

    def close(self) -> None:
        self._release_capture()
        self._image_frame = None
        self._opened = False
        self._closed = True

    def read(self) -> Frame | None:
        if self._closed:
            raise FrameSourceClosed("Cannot read from a closed OpenCVFrameSource.")
        if not self._opened:
            raise FrameSourceClosed("OpenCVFrameSource is not open; call open() first.")

        if self._is_image:
            return self._read_image_once()

        assert self._capture is not None
        ok, mat = self._capture.read()
        if not ok or mat is None:
            if self._is_stream:
                if self._try_reconnect():
                    ok, mat = self._capture.read()
                    if not ok or mat is None:
                        logger.warning(
                            "Stream %s failed after reconnect attempts; ending.",
                            self.safe_source_label,
                        )
                        return None
                else:
                    return None
            else:
                # Finite video / camera EOF.
                return None

        return self._pack_frame(mat)

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

    def _open_capture(self) -> None:
        if self._is_image:
            assert isinstance(self._raw_source, str)
            mat = cv2.imread(self._raw_source, cv2.IMREAD_COLOR)
            if mat is None:
                raise FrameSourceError(f"Failed to read image: {self.safe_source_label}")
            self._image_frame = np.asarray(mat, dtype=np.uint8)
            logger.info("Opened image source %s", self.safe_source_label)
            return

        capture = cv2.VideoCapture(self._raw_source)
        if not capture.isOpened():
            capture.release()
            raise FrameSourceError(f"Failed to open capture: {self.safe_source_label}")
        self._capture = capture
        logger.info("Opened capture source %s", self.safe_source_label)

    def _release_capture(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None
            logger.debug("Released capture %s", self.safe_source_label)

    def _read_image_once(self) -> Frame | None:
        if self._image_consumed:
            return None
        if self._image_frame is None:
            raise FrameSourceError("Image source has no loaded frame.")
        frame = self._pack_frame(self._image_frame)
        self._image_consumed = True
        return frame

    def _try_reconnect(self) -> bool:
        attempts = self._reconnect.max_attempts
        if attempts <= 0:
            logger.warning(
                "Stream %s disconnected; reconnect disabled (max_attempts=0).",
                self.safe_source_label,
            )
            return False

        for attempt in range(1, attempts + 1):
            logger.warning(
                "Stream %s disconnected; reconnect attempt %s/%s after %.2fs",
                self.safe_source_label,
                attempt,
                attempts,
                self._reconnect.delay_seconds,
            )
            if self._reconnect.delay_seconds > 0:
                self._sleep(self._reconnect.delay_seconds)
            self._release_capture()
            try:
                self._open_capture()
            except FrameSourceError:
                logger.warning(
                    "Reconnect attempt %s/%s failed for %s",
                    attempt,
                    attempts,
                    self.safe_source_label,
                )
                continue
            if self._capture is not None and self._capture.isOpened():
                logger.info(
                    "Reconnected stream %s on attempt %s",
                    self.safe_source_label,
                    attempt,
                )
                return True

        logger.error(
            "Exhausted %s reconnect attempts for %s",
            attempts,
            self.safe_source_label,
        )
        return False

    def _pack_frame(self, mat: Any) -> Frame:
        array = cast(ImageArray, np.asarray(mat))
        if array.ndim == 2:
            array = cast(ImageArray, cv2.cvtColor(array, cv2.COLOR_GRAY2BGR))
        image = cast(ImageArray, np.ascontiguousarray(array, dtype=np.uint8))
        height, width = int(image.shape[0]), int(image.shape[1])
        metadata = FrameMetadata(
            timestamp=datetime.now(tz=UTC),
            index=self._index,
            source_id=self._source_id,
            width=width,
            height=height,
        )
        frame = Frame(image=image, metadata=metadata)
        self._index += 1
        return frame


def _default_source_id(source: str | int) -> str:
    if isinstance(source, int):
        return f"webcam-{source}"
    if _is_stream_uri(source):
        return f"stream:{redact_source_uri(source)}"
    return Path(source).name or "opencv-source"

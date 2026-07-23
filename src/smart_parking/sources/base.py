"""Frame source protocol and metadata (OpenCV-agnostic)."""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

import numpy as np
from numpy.typing import NDArray

# BGR uint8 image as produced by OpenCV VideoCapture / imread adapters.
ImageArray = NDArray[np.uint8]

_CREDENTIAL_IN_URI = re.compile(
    r"^(?P<scheme>[a-zA-Z][a-zA-Z0-9+.-]*://)"
    r"(?P<user>[^:/@]+):(?P<password>[^@]+)@"
    r"(?P<rest>.+)$"
)


class FrameSourceError(Exception):
    """Base error for frame source failures."""


class FrameSourceEOF(FrameSourceError):
    """Raised when a source has no more frames (file ended or image exhausted)."""


class FrameSourceClosed(FrameSourceError):
    """Raised when operations are attempted after the source was closed."""


@dataclass(frozen=True, slots=True)
class FrameMetadata:
    """Per-frame provenance and geometry."""

    timestamp: datetime
    index: int
    source_id: str
    width: int
    height: int

    def __post_init__(self) -> None:
        if self.index < 0:
            raise ValueError(f"frame index must be >= 0, got {self.index}.")
        if self.width <= 0 or self.height <= 0:
            raise ValueError(f"frame dimensions must be positive, got {self.width}x{self.height}.")
        if not self.source_id.strip():
            raise ValueError("source_id must be a non-empty string.")
        if self.timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware (UTC expected).")


@dataclass(frozen=True, slots=True)
class Frame:
    """Single decoded frame plus metadata.

    ``image`` is a BGR ``uint8`` array shaped ``(H, W, 3)``. Callers must not
    mutate shared buffers after yielding unless the source documents ownership.
    """

    image: ImageArray
    metadata: FrameMetadata

    def __post_init__(self) -> None:
        if self.image.ndim != 3 or self.image.shape[2] != 3:
            raise ValueError(f"image must be HxWx3, got shape {self.image.shape}.")
        height, width = int(self.image.shape[0]), int(self.image.shape[1])
        if height != self.metadata.height or width != self.metadata.width:
            raise ValueError(
                "image shape does not match metadata dimensions: "
                f"image={width}x{height}, metadata={self.metadata.width}x{self.metadata.height}."
            )


@dataclass(frozen=True, slots=True)
class ReconnectPolicy:
    """Bounded reconnect behaviour for live streams."""

    max_attempts: int = 3
    delay_seconds: float = 1.0

    def __post_init__(self) -> None:
        if self.max_attempts < 0:
            raise ValueError(f"max_attempts must be >= 0, got {self.max_attempts}.")
        if self.delay_seconds < 0.0:
            raise ValueError(f"delay_seconds must be >= 0, got {self.delay_seconds}.")


def redact_source_uri(uri: str) -> str:
    """Redact userinfo credentials from URLs used in logs.

    Examples:
        ``rtsp://user:secret@host/path`` → ``rtsp://***:***@host/path``
    """
    match = _CREDENTIAL_IN_URI.match(uri)
    if not match:
        return uri
    return f"{match.group('scheme')}***:***@{match.group('rest')}"


@runtime_checkable
class FrameSource(Protocol):
    """Common iterator interface for image, video, webcam, stream, and synthetic sources."""

    @property
    def source_id(self) -> str:
        """Stable identifier for this capture endpoint."""

    @property
    def is_open(self) -> bool:
        """Whether the underlying capture resource is open."""

    def open(self) -> None:
        """Acquire capture resources."""

    def close(self) -> None:
        """Release capture resources (idempotent)."""

    def read(self) -> Frame | None:
        """Return the next frame, or ``None`` at EOF for finite sources."""

    def __iter__(self) -> Iterator[Frame]:
        """Yield frames until EOF, ensuring cleanup."""

    def __enter__(self) -> FrameSource:
        """Open the source for context-manager use."""

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object,
    ) -> None:
        """Close the source when leaving the context."""

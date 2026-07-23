"""Unit tests for frame sources, EOF handling, cleanup, and URI redaction."""

from __future__ import annotations

from datetime import UTC
from pathlib import Path
from unittest.mock import MagicMock

import cv2
import numpy as np
import pytest

from smart_parking.sources import (
    Frame,
    FrameMetadata,
    FrameSourceClosed,
    FrameSourceError,
    ReconnectPolicy,
    SyntheticFrameSource,
    redact_source_uri,
)
from smart_parking.sources.factory import create_frame_source
from smart_parking.sources.opencv_source import OpenCVFrameSource


def test_redact_source_uri_strips_credentials() -> None:
    uri = "rtsp://admin:s3cret@192.168.1.10:554/cam/realmonitor"
    assert redact_source_uri(uri) == "rtsp://***:***@192.168.1.10:554/cam/realmonitor"
    assert "s3cret" not in redact_source_uri(uri)
    assert redact_source_uri("file:///tmp/video.mp4") == "file:///tmp/video.mp4"
    assert redact_source_uri("rtsp://host/no-creds") == "rtsp://host/no-creds"


def test_synthetic_source_iterates_and_cleans_up() -> None:
    source = SyntheticFrameSource(
        source_id="synth-a",
        width=32,
        height=24,
        frame_count=5,
        moving_rectangle=True,
    )
    frames = list(source)
    assert len(frames) == 5
    assert all(isinstance(f, Frame) for f in frames)
    assert frames[0].metadata.source_id == "synth-a"
    assert frames[0].metadata.width == 32
    assert frames[0].metadata.height == 24
    assert frames[0].metadata.timestamp.tzinfo is not None
    assert frames[0].metadata.timestamp.tzinfo == UTC or (
        frames[0].metadata.timestamp.utcoffset() is not None
    )
    assert frames[-1].metadata.index == 4
    assert not source.is_open
    assert source._closed  # noqa: SLF001 — cleanup contract


def test_synthetic_context_manager_releases() -> None:
    with SyntheticFrameSource(frame_count=2) as source:
        assert source.is_open
        assert source.read() is not None
    assert not source.is_open
    with pytest.raises(FrameSourceClosed):
        source.read()


def test_synthetic_eof_returns_none() -> None:
    source = SyntheticFrameSource(frame_count=1)
    source.open()
    assert source.read() is not None
    assert source.read() is None
    source.close()


def test_frame_metadata_rejects_naive_timestamp() -> None:
    from datetime import datetime

    with pytest.raises(ValueError, match="timezone-aware"):
        FrameMetadata(
            timestamp=datetime(2026, 7, 23, 15, 0, 0),
            index=0,
            source_id="x",
            width=10,
            height=10,
        )


def test_opencv_image_path(tmp_path: Path) -> None:
    image_path = tmp_path / "frame.png"
    mat = np.zeros((20, 30, 3), dtype=np.uint8)
    mat[:, :] = (10, 20, 30)
    assert cv2.imwrite(str(image_path), mat)

    source = OpenCVFrameSource(str(image_path), source_id="img-1")
    frames = list(source)
    assert len(frames) == 1
    assert frames[0].metadata.width == 30
    assert frames[0].metadata.height == 20
    assert frames[0].metadata.source_id == "img-1"
    assert not source.is_open


def test_opencv_video_path_and_eof(tmp_path: Path) -> None:
    video_path = tmp_path / "clip.avi"
    writer = cv2.VideoWriter(
        str(video_path),
        cv2.VideoWriter_fourcc(*"MJPG"),
        5.0,
        (40, 30),
    )
    assert writer.isOpened()
    for i in range(4):
        frame = np.full((30, 40, 3), i * 40, dtype=np.uint8)
        writer.write(frame)
    writer.release()

    source = OpenCVFrameSource(str(video_path), source_id="vid-1")
    frames = list(source)
    assert len(frames) == 4
    assert frames[0].metadata.index == 0
    assert frames[-1].metadata.index == 3
    assert not source.is_open

    # Re-open finite video and confirm EOF via read().
    source2 = OpenCVFrameSource(str(video_path))
    source2.open()
    count = 0
    while source2.read() is not None:
        count += 1
    assert count == 4
    assert source2.read() is None
    source2.close()
    assert source2._capture is None  # noqa: SLF001 — release contract


def test_opencv_release_on_open_failure() -> None:
    source = OpenCVFrameSource("definitely-missing-file-xyz.mp4")
    with pytest.raises(FrameSourceError, match="Failed to open capture"):
        source.open()
    assert source._capture is None  # noqa: SLF001
    assert not source.is_open


def test_opencv_safe_label_redacts_credentials() -> None:
    source = OpenCVFrameSource("rtsp://user:pass@cam.example/stream1")
    assert "pass" not in source.safe_source_label
    assert "***:***" in source.safe_source_label


def test_reconnect_bounded_with_injectable_sleep() -> None:
    sleeps: list[float] = []

    def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    source = OpenCVFrameSource(
        "rtsp://user:secret@cam.example/live",
        reconnect=ReconnectPolicy(max_attempts=2, delay_seconds=0.05),
        sleep=fake_sleep,
    )
    source._is_stream = True  # noqa: SLF001
    source._opened = True  # noqa: SLF001
    source._closed = False  # noqa: SLF001

    failing = MagicMock()
    failing.read.return_value = (False, None)
    failing.isOpened.return_value = False
    source._capture = failing  # noqa: SLF001

    open_calls = {"n": 0}

    def always_fail() -> None:
        open_calls["n"] += 1
        raise FrameSourceError("reconnect failed")

    source._open_capture = always_fail  # type: ignore[method-assign]

    result = source.read()
    assert result is None
    assert open_calls["n"] == 2
    assert sleeps == [0.05, 0.05]
    assert source._capture is None  # noqa: SLF001 — released after failures


def test_reconnect_disabled_when_max_attempts_zero() -> None:
    source = OpenCVFrameSource(
        "rtsp://host/stream",
        reconnect=ReconnectPolicy(max_attempts=0, delay_seconds=1.0),
    )
    source._is_stream = True  # noqa: SLF001
    source._opened = True  # noqa: SLF001
    failing = MagicMock()
    failing.read.return_value = (False, None)
    source._capture = failing  # noqa: SLF001
    assert source.read() is None


def test_factory_synthetic_and_path(tmp_path: Path) -> None:
    synth = create_frame_source("synthetic:16:12:3", source_id="f")
    assert isinstance(synth, SyntheticFrameSource)
    assert len(list(synth)) == 3

    image_path = tmp_path / "one.jpg"
    cv2.imwrite(str(image_path), np.zeros((8, 8, 3), dtype=np.uint8))
    opened = create_frame_source(str(image_path))
    assert isinstance(opened, OpenCVFrameSource)
    assert len(list(opened)) == 1


def test_reconnect_policy_validation() -> None:
    with pytest.raises(ValueError):
        ReconnectPolicy(max_attempts=-1)
    with pytest.raises(ValueError):
        ReconnectPolicy(delay_seconds=-0.1)

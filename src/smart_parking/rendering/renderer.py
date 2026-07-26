"""Annotation renderer — drawing only, no occupancy business logic."""

from __future__ import annotations

from collections.abc import Sequence

import cv2
import numpy as np
from numpy.typing import NDArray

from smart_parking.domain.parking import Detection, ParkingMap, ParkingSpace
from smart_parking.domain.state import OccupancySnapshot, OccupancyState, SpaceOccupancy
from smart_parking.pipeline.snapshot import PipelineMetrics
from smart_parking.rendering.colors import DETECTION, HUD_BG, TEXT, color_for_state

ImageArray = NDArray[np.uint8]


def _space_lookup(snapshot: OccupancySnapshot) -> dict[str, SpaceOccupancy]:
    return {space.space_id: space for space in snapshot.spaces}


def _draw_polygon(
    canvas: ImageArray,
    space: ParkingSpace,
    state: OccupancyState,
    *,
    alpha: float = 0.35,
) -> None:
    color = color_for_state(state)
    pts = np.array([[int(p.x), int(p.y)] for p in space.polygon], dtype=np.int32)
    if pts.shape[0] < 3:
        return
    overlay = canvas.copy()
    cv2.fillPoly(overlay, [pts], color)
    cv2.addWeighted(overlay, alpha, canvas, 1.0 - alpha, 0, canvas)
    cv2.polylines(canvas, [pts], isClosed=True, color=color, thickness=2)


def _draw_space_label(
    canvas: ImageArray,
    space: ParkingSpace,
    occupancy: SpaceOccupancy | None,
) -> None:
    if not space.polygon:
        return
    xs = [p.x for p in space.polygon]
    ys = [p.y for p in space.polygon]
    x = int(min(xs))
    y = max(int(min(ys)) - 6, 14)
    state = occupancy.state if occupancy is not None else OccupancyState.UNKNOWN
    confidence = occupancy.confidence if occupancy is not None else 0.0
    track = occupancy.track_id if occupancy is not None else None
    label = f"{space.label} {state} {confidence:.2f}"
    if track:
        label = f"{label} id={track}"
    cv2.putText(
        canvas,
        label,
        (x, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        TEXT,
        1,
        cv2.LINE_AA,
    )


def _draw_detection(canvas: ImageArray, detection: Detection) -> None:
    x1, y1, x2, y2 = (int(v) for v in detection.bbox.as_xyxy())
    cv2.rectangle(canvas, (x1, y1), (x2, y2), DETECTION, 2)
    parts = [detection.class_name, f"{detection.confidence:.2f}"]
    if detection.track_id:
        parts.append(f"#{detection.track_id}")
    label = " ".join(parts)
    cv2.putText(
        canvas,
        label,
        (x1, max(y1 - 4, 12)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        DETECTION,
        1,
        cv2.LINE_AA,
    )


def _draw_hud(
    canvas: ImageArray,
    snapshot: OccupancySnapshot,
    metrics: PipelineMetrics | None,
) -> None:
    lines = [
        f"cam={snapshot.camera_id} frame={snapshot.frame_index}",
        (
            f"avail={snapshot.available} occ={snapshot.occupied} "
            f"unk={snapshot.unknown} occ%={snapshot.occupancy_percent:.1f}"
        ),
    ]
    if metrics is not None:
        lines.append(
            f"fps e2e={metrics.e2e_fps:.1f} decode={metrics.decode_fps:.1f} "
            f"infer={metrics.inference_fps:.1f}"
        )
    pad = 6
    line_h = 18
    box_h = pad * 2 + line_h * len(lines)
    box_w = max(320, canvas.shape[1] // 2)
    cv2.rectangle(canvas, (0, 0), (box_w, box_h), HUD_BG, thickness=-1)
    for i, line in enumerate(lines):
        cv2.putText(
            canvas,
            line,
            (pad, pad + line_h * (i + 1) - 4),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            TEXT,
            1,
            cv2.LINE_AA,
        )


def render_frame(
    image: ImageArray,
    parking_map: ParkingMap,
    snapshot: OccupancySnapshot,
    detections: Sequence[Detection] = (),
    metrics: PipelineMetrics | None = None,
    *,
    draw_detections: bool = True,
    draw_hud: bool = True,
) -> ImageArray:
    """Draw parking spaces, confirmed state, detections, and summary metrics.

    The renderer never computes occupancy — it only visualizes the snapshot
    produced by the occupancy engine.
    """
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError(f"image must be HxWx3 BGR, got shape {image.shape}.")
    canvas = image.copy()
    by_id = _space_lookup(snapshot)

    for space in parking_map.spaces:
        if not space.enabled:
            continue
        occupancy = by_id.get(space.id)
        state = occupancy.state if occupancy is not None else OccupancyState.UNKNOWN
        _draw_polygon(canvas, space, state)
        _draw_space_label(canvas, space, occupancy)

    if draw_detections:
        for detection in detections:
            _draw_detection(canvas, detection)

    if draw_hud:
        _draw_hud(canvas, snapshot, metrics)

    return canvas


class AnnotationRenderer:
    """Callable renderer compatible with ``ParkingProcessor.render_fn``."""

    def __init__(
        self,
        *,
        draw_detections: bool = True,
        draw_hud: bool = True,
    ) -> None:
        self._draw_detections = draw_detections
        self._draw_hud = draw_hud

    def __call__(
        self,
        image: ImageArray,
        parking_map: ParkingMap,
        snapshot: OccupancySnapshot,
        detections: Sequence[Detection],
        metrics: PipelineMetrics,
    ) -> ImageArray:
        return render_frame(
            image,
            parking_map,
            snapshot,
            detections,
            metrics,
            draw_detections=self._draw_detections,
            draw_hud=self._draw_hud,
        )

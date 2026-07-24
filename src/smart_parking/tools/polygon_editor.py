"""Interactive parking-space polygon editor (headless core + OpenCV UI)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from smart_parking.config.loader import ConfigError, load_parking_map
from smart_parking.domain.parking import ParkingMap, ParkingSpace, Point
from smart_parking.spaces.serialize import save_parking_map, scale_parking_map
from smart_parking.spaces.validation import PolygonValidationError, validate_parking_map


@dataclass
class EditorSpaceDraft:
    """Mutable draft of a parking space while editing."""

    id: str
    label: str
    points: list[Point] = field(default_factory=list)
    zone: str | None = None
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def undo_point(self) -> Point | None:
        if not self.points:
            return None
        return self.points.pop()

    def add_point(self, point: Point) -> None:
        self.points.append(point)

    def to_parking_space(self) -> ParkingSpace:
        return ParkingSpace(
            id=self.id,
            label=self.label,
            polygon=tuple(self.points),
            zone=self.zone,
            enabled=self.enabled,
            metadata=dict(self.metadata),
        )


@dataclass
class ParkingMapEditor:
    """Headless parking-map editor state machine.

    Interactive UI (OpenCV) wraps this class; unit tests exercise these methods
    without a display.
    """

    camera_id: str
    reference_width: int
    reference_height: int
    spaces: list[EditorSpaceDraft] = field(default_factory=list)
    active_index: int | None = None
    status_message: str = ""

    @classmethod
    def create_empty(
        cls,
        *,
        camera_id: str,
        reference_width: int,
        reference_height: int,
    ) -> ParkingMapEditor:
        return cls(
            camera_id=camera_id,
            reference_width=reference_width,
            reference_height=reference_height,
        )

    @classmethod
    def from_parking_map(cls, parking_map: ParkingMap) -> ParkingMapEditor:
        drafts = [
            EditorSpaceDraft(
                id=space.id,
                label=space.label,
                points=list(space.polygon),
                zone=space.zone,
                enabled=space.enabled,
                metadata=dict(space.metadata),
            )
            for space in parking_map.spaces
        ]
        return cls(
            camera_id=parking_map.camera_id,
            reference_width=parking_map.reference_width,
            reference_height=parking_map.reference_height,
            spaces=drafts,
            active_index=0 if drafts else None,
        )

    @property
    def active_space(self) -> EditorSpaceDraft | None:
        if self.active_index is None:
            return None
        if not (0 <= self.active_index < len(self.spaces)):
            return None
        return self.spaces[self.active_index]

    def start_space(
        self,
        space_id: str,
        label: str | None = None,
        *,
        zone: str | None = None,
    ) -> EditorSpaceDraft:
        """Begin a new space draft and make it active."""
        if not space_id.strip():
            raise ValueError("Space id must be a non-empty string.")
        if any(space.id == space_id for space in self.spaces):
            raise ValueError(f"Duplicate parking space id '{space_id}'.")
        draft = EditorSpaceDraft(
            id=space_id,
            label=(label or space_id).strip() or space_id,
            zone=zone,
        )
        self.spaces.append(draft)
        self.active_index = len(self.spaces) - 1
        self.status_message = f"Started space {space_id}"
        return draft

    def select_space(self, index: int) -> EditorSpaceDraft:
        if not (0 <= index < len(self.spaces)):
            raise IndexError(f"Space index {index} out of range.")
        self.active_index = index
        self.status_message = f"Selected space {self.spaces[index].id}"
        return self.spaces[index]

    def select_space_by_id(self, space_id: str) -> EditorSpaceDraft:
        for index, space in enumerate(self.spaces):
            if space.id == space_id:
                return self.select_space(index)
        raise KeyError(f"Unknown parking space id '{space_id}'.")

    def add_point(self, x: float, y: float) -> Point:
        active = self.active_space
        if active is None:
            raise RuntimeError("No active space. Start or select a space first.")
        if not (0.0 <= x <= float(self.reference_width)):
            raise ValueError(f"Point x={x} is outside reference width [0, {self.reference_width}].")
        if not (0.0 <= y <= float(self.reference_height)):
            raise ValueError(
                f"Point y={y} is outside reference height [0, {self.reference_height}]."
            )
        point = Point(float(x), float(y))
        active.add_point(point)
        self.status_message = f"Added point ({x:.1f}, {y:.1f}) to {active.id}"
        return point

    def undo_point(self) -> Point | None:
        active = self.active_space
        if active is None:
            return None
        removed = active.undo_point()
        if removed is not None:
            self.status_message = f"Undid point on {active.id}"
        return removed

    def delete_active_space(self) -> EditorSpaceDraft | None:
        if self.active_index is None or not self.spaces:
            return None
        removed = self.spaces.pop(self.active_index)
        if not self.spaces:
            self.active_index = None
        else:
            self.active_index = min(self.active_index, len(self.spaces) - 1)
        self.status_message = f"Deleted space {removed.id}"
        return removed

    def set_active_enabled(self, enabled: bool) -> None:
        active = self.active_space
        if active is None:
            raise RuntimeError("No active space.")
        active.enabled = enabled
        state = "enabled" if enabled else "disabled"
        self.status_message = f"Space {active.id} {state}"

    def rename_active(self, *, space_id: str | None = None, label: str | None = None) -> None:
        active = self.active_space
        if active is None:
            raise RuntimeError("No active space.")
        if space_id is not None:
            cleaned = space_id.strip()
            if not cleaned:
                raise ValueError("Space id must be a non-empty string.")
            if any(s.id == cleaned and s is not active for s in self.spaces):
                raise ValueError(f"Duplicate parking space id '{cleaned}'.")
            active.id = cleaned
        if label is not None:
            cleaned_label = label.strip()
            if not cleaned_label:
                raise ValueError("Space label must be a non-empty string.")
            active.label = cleaned_label
        self.status_message = f"Renamed space to {active.id} / {active.label}"

    def to_parking_map(self, *, validate: bool = True) -> ParkingMap:
        """Build a ParkingMap from drafts.

        Incomplete drafts (< 3 points) raise PolygonValidationError when validate=True.
        """
        completed: list[ParkingSpace] = []
        for draft in self.spaces:
            if len(draft.points) < 3:
                if validate:
                    msg = (
                        f"Parking space '{draft.id}' polygon needs at least 3 points, "
                        f"got {len(draft.points)}. Finish drawing before saving."
                    )
                    raise PolygonValidationError(msg)
                continue
            completed.append(draft.to_parking_space())

        parking_map = ParkingMap(
            camera_id=self.camera_id,
            reference_width=self.reference_width,
            reference_height=self.reference_height,
            spaces=tuple(completed),
        )
        if validate:
            validate_parking_map(parking_map)
        return parking_map

    def save(self, path: Path | str, *, validate: bool = True) -> Path:
        parking_map = self.to_parking_map(validate=validate)
        out = save_parking_map(parking_map, path, validate=validate)
        self.status_message = f"Saved {out}"
        return out

    def scale_to(self, *, target_width: int, target_height: int) -> ParkingMapEditor:
        """Return a new editor with spaces scaled to a different resolution."""
        parking_map = self.to_parking_map(validate=True)
        scaled = scale_parking_map(
            parking_map,
            target_width=target_width,
            target_height=target_height,
        )
        return ParkingMapEditor.from_parking_map(scaled)


def display_available() -> bool:
    """Return True when an interactive OpenCV window is likely available."""
    if os.environ.get("SMART_PARKING_FORCE_HEADLESS", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }:
        return False
    if os.environ.get("CI", "").strip():
        return False
    # Windows typically has a desktop session; Unix needs DISPLAY/WAYLAND.
    if os.name == "nt":
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def _load_reference_image(source: Path) -> np.ndarray:
    image = cv2.imread(str(source), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(f"Could not read reference image/video frame: {source}")
    return image


def _extract_first_frame(source: Path) -> np.ndarray:
    """Load an image, or the first frame of a video file."""
    suffix = source.suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}:
        return _load_reference_image(source)

    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        # Fall back to image decode for unusual extensions.
        return _load_reference_image(source)
    try:
        ok, frame = capture.read()
        if not ok or frame is None:
            raise FileNotFoundError(f"Could not read first frame from: {source}")
        return frame
    finally:
        capture.release()


def _draw_overlay(base: np.ndarray, editor: ParkingMapEditor) -> np.ndarray:
    canvas = base.copy()
    for index, space in enumerate(editor.spaces):
        is_active = index == editor.active_index
        color = (0, 255, 0) if space.enabled else (80, 80, 80)
        if is_active:
            color = (0, 220, 255)
        pts = space.points
        if len(pts) >= 2:
            arr = np.array([[int(p.x), int(p.y)] for p in pts], dtype=np.int32)
            cv2.polylines(canvas, [arr], isClosed=len(pts) >= 3, color=color, thickness=2)
        for point in pts:
            cv2.circle(canvas, (int(point.x), int(point.y)), 4, color, -1)
        if pts:
            label = f"{space.id}" + ("" if space.enabled else " [off]")
            cv2.putText(
                canvas,
                label,
                (int(pts[0].x), max(16, int(pts[0].y) - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                1,
                cv2.LINE_AA,
            )

    help_lines = [
        "LMB: add point | u: undo | n: new space | d: delete space | e: toggle enable",
        "s: save | [/]: prev/next space | q/ESC: quit | h: help in terminal",
        editor.status_message,
    ]
    y = 20
    for line in help_lines:
        cv2.putText(
            canvas,
            line,
            (10, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
        y += 18
    return canvas


def build_editor_for_frame(
    frame: np.ndarray,
    *,
    camera_id: str = "camera-01",
    existing_map: Path | str | None = None,
    scale_to_source: bool = True,
) -> ParkingMapEditor:
    """Create an editor bound to a reference frame's resolution."""
    height, width = frame.shape[:2]
    if existing_map is not None:
        loaded = load_parking_map(existing_map)
        if scale_to_source and (
            loaded.reference_width != width or loaded.reference_height != height
        ):
            loaded = scale_parking_map(loaded, target_width=width, target_height=height)
        editor = ParkingMapEditor.from_parking_map(loaded)
        editor.camera_id = loaded.camera_id or camera_id
    else:
        editor = ParkingMapEditor.create_empty(
            camera_id=camera_id,
            reference_width=width,
            reference_height=height,
        )
    editor.reference_width = width
    editor.reference_height = height
    return editor


def handle_editor_click(editor: ParkingMapEditor, x: float, y: float) -> None:
    """Apply a left-click: auto-start a space if needed, then add a vertex."""
    if editor.active_space is None:
        next_id = f"S{len(editor.spaces) + 1}"
        try:
            editor.start_space(next_id)
        except ValueError as exc:
            editor.status_message = str(exc)
            return
    try:
        editor.add_point(float(x), float(y))
    except (ValueError, RuntimeError) as exc:
        editor.status_message = str(exc)


def handle_editor_key(
    editor: ParkingMapEditor,
    key: int,
    *,
    output_path: Path,
    prompt_new_space: bool = False,
) -> tuple[bool, Path | None]:
    """Handle one keypress. Returns ``(should_quit, saved_path_or_none)``.

    When ``prompt_new_space`` is False (tests), ``n`` starts ``S{n}`` without stdin.
    """
    if key in {27, ord("q")}:
        return True, None
    if key == ord("u"):
        editor.undo_point()
    elif key == ord("d"):
        editor.delete_active_space()
    elif key == ord("e"):
        active = editor.active_space
        if active is not None:
            editor.set_active_enabled(not active.enabled)
    elif key == ord("["):
        if editor.spaces:
            idx = editor.active_index or 0
            editor.select_space((idx - 1) % len(editor.spaces))
    elif key == ord("]"):
        if editor.spaces:
            idx = editor.active_index or 0
            editor.select_space((idx + 1) % len(editor.spaces))
    elif key == ord("n"):
        try:
            if prompt_new_space:  # pragma: no cover - requires interactive stdin
                space_id = input("New space id: ").strip()
                label = input("Label (blank = id): ").strip() or None
                zone = input("Zone (blank = none): ").strip() or None
                editor.start_space(space_id, label, zone=zone)
            else:
                editor.start_space(f"S{len(editor.spaces) + 1}")
        except (ValueError, EOFError) as exc:
            editor.status_message = str(exc)
    elif key == ord("s"):
        try:
            return False, editor.save(output_path)
        except (PolygonValidationError, ConfigError, ValueError) as exc:
            editor.status_message = f"Save failed: {exc}"
    return False, None


def run_polygon_editor(
    *,
    source: Path | str,
    output: Path | str,
    camera_id: str = "camera-01",
    existing_map: Path | str | None = None,
    scale_to_source: bool = True,
) -> Path:
    """Launch the OpenCV desktop polygon editor.

    Raises RuntimeError when no display is available. Pure editing logic lives in
    :class:`ParkingMapEditor` and can be tested without a GUI.
    """
    if not display_available():
        raise RuntimeError(
            "No interactive display available for the polygon editor. "
            "Use ParkingMapEditor programmatically, or unset SMART_PARKING_FORCE_HEADLESS / "
            "run on a machine with a desktop session."
        )

    source_path = Path(source)
    if not source_path.is_file():
        raise FileNotFoundError(f"Reference source not found: {source_path}")

    frame = _extract_first_frame(source_path)
    editor = build_editor_for_frame(
        frame,
        camera_id=camera_id,
        existing_map=existing_map,
        scale_to_source=scale_to_source,
    )
    return _run_opencv_ui(frame, editor, output_path=Path(output))


def _run_opencv_ui(  # pragma: no cover - requires interactive display
    frame: np.ndarray,
    editor: ParkingMapEditor,
    *,
    output_path: Path,
) -> Path:
    """OpenCV window event loop (skipped in coverage; exercised manually)."""
    window = "smart-parking polygon editor"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)

    def on_mouse(event: int, x: int, y: int, _flags: int, _userdata: object) -> None:
        if event == cv2.EVENT_LBUTTONDOWN:
            handle_editor_click(editor, float(x), float(y))

    cv2.setMouseCallback(window, on_mouse)
    saved_path: Path | None = None

    print("Polygon editor controls:")
    print("  LMB          add vertex to active space")
    print("  u            undo last vertex")
    print("  n            start a new space (prompts in terminal)")
    print("  d            delete active space")
    print("  e            toggle enabled on active space")
    print("  [ / ]        previous / next space")
    print("  s            save validated JSON")
    print("  q / ESC      quit")

    while True:
        overlay = _draw_overlay(frame, editor)
        cv2.imshow(window, overlay)
        key = cv2.waitKey(30) & 0xFF
        should_quit, maybe_saved = handle_editor_key(
            editor,
            key,
            output_path=output_path,
            prompt_new_space=True,
        )
        if maybe_saved is not None:
            saved_path = maybe_saved
            print(f"Saved parking map to {saved_path}")
        if should_quit:
            break

    cv2.destroyWindow(window)
    if saved_path is None:
        try:
            saved_path = editor.save(output_path)
            print(f"Saved parking map to {saved_path}")
        except (PolygonValidationError, ConfigError, ValueError) as exc:
            raise SystemExit(f"Editor closed without a valid save: {exc}") from exc
    return saved_path

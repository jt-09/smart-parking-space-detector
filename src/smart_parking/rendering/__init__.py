"""Annotation rendering package (drawing only)."""

from smart_parking.rendering.colors import STATE_COLORS, color_for_state
from smart_parking.rendering.renderer import AnnotationRenderer, render_frame

__all__ = [
    "AnnotationRenderer",
    "STATE_COLORS",
    "color_for_state",
    "render_frame",
]

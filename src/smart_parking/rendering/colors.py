"""BGR colors for occupancy annotation overlays."""

from __future__ import annotations

from smart_parking.domain.state import OccupancyState

# OpenCV uses BGR tuples.
ColorBGR = tuple[int, int, int]

AVAILABLE = (80, 180, 80)
OCCUPIED = (60, 60, 220)
UNKNOWN = (128, 128, 128)
PENDING_OCCUPIED = (40, 180, 220)
PENDING_AVAILABLE = (40, 200, 255)
DETECTION = (255, 180, 40)
TEXT = (240, 240, 240)
HUD_BG = (32, 32, 32)

STATE_COLORS: dict[OccupancyState, ColorBGR] = {
    OccupancyState.AVAILABLE: AVAILABLE,
    OccupancyState.OCCUPIED: OCCUPIED,
    OccupancyState.UNKNOWN: UNKNOWN,
    OccupancyState.PENDING_OCCUPIED: PENDING_OCCUPIED,
    OccupancyState.PENDING_AVAILABLE: PENDING_AVAILABLE,
}


def color_for_state(state: OccupancyState) -> ColorBGR:
    """Return the overlay color for a confirmed/pending occupancy state."""
    return STATE_COLORS.get(state, UNKNOWN)

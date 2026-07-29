"""Smart Parking-Space Detector package."""

from importlib.metadata import PackageNotFoundError, version

__all__ = ["__version__"]

try:
    __version__ = version("smart-parking")
except PackageNotFoundError:  # pragma: no cover - editable/dev fallback
    __version__ = "1.0.0"

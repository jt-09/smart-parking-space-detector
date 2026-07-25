"""Processing pipeline package."""

from smart_parking.pipeline.processor import (
    FrameProcessResult,
    ParkingProcessor,
    PipelineResult,
    create_detector,
)
from smart_parking.pipeline.snapshot import PipelineMetrics, snapshot_to_dict, space_occupancy_to_dict

__all__ = [
    "FrameProcessResult",
    "ParkingProcessor",
    "PipelineMetrics",
    "PipelineResult",
    "create_detector",
    "snapshot_to_dict",
    "space_occupancy_to_dict",
]

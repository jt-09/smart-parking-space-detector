"""Processing pipeline package."""

from smart_parking.pipeline.processor import (
    FrameProcessResult,
    ParkingProcessor,
    PipelineResult,
    create_detector,
)
from smart_parking.pipeline.snapshot import PipelineMetrics, snapshot_to_dict, space_occupancy_to_dict
from smart_parking.pipeline.writers import (
    AnnotatedVideoWriter,
    JsonlSnapshotWriter,
    build_output_paths,
    ensure_output_dir,
    write_metrics_json,
)

__all__ = [
    "AnnotatedVideoWriter",
    "FrameProcessResult",
    "JsonlSnapshotWriter",
    "ParkingProcessor",
    "PipelineMetrics",
    "PipelineResult",
    "build_output_paths",
    "create_detector",
    "ensure_output_dir",
    "snapshot_to_dict",
    "space_occupancy_to_dict",
    "write_metrics_json",
]

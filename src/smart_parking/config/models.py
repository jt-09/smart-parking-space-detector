"""Pydantic configuration models matching SETUP.md layered settings."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class AppSettings(BaseModel):
    """Application runtime settings."""

    environment: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    output_dir: Path = Path("output")


class CameraSettings(BaseModel):
    """Camera / frame source settings."""

    id: str = "lot-a-camera-01"
    source: str = "data/sample.mp4"
    reconnect_seconds: float = Field(default=5.0, ge=0.0)
    max_frame_age_seconds: float = Field(default=3.0, gt=0.0)

    @field_validator("id")
    @classmethod
    def _non_empty_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("camera.id must be a non-empty string.")
        return value


class VideoSettings(BaseModel):
    """Frame sampling and output video settings."""

    process_every_n_frames: int = Field(default=1, ge=1)
    output_fps: float | None = Field(default=None, gt=0.0)
    resize_width: int | None = Field(default=None, gt=0)
    display: bool = False
    save_annotated_video: bool = True


class ModelSettings(BaseModel):
    """Detector model settings (backend-agnostic)."""

    name: str = "yolo26n.pt"
    device: str = "cpu"
    confidence: float = Field(default=0.30, ge=0.0, le=1.0)
    iou: float = Field(default=0.50, ge=0.0, le=1.0)
    allowed_classes: list[str] = Field(
        default_factory=lambda: ["car", "motorcycle", "bus", "truck"]
    )
    tracking_enabled: bool = True
    tracker: str | None = None


class GeometrySettings(BaseModel):
    """Parking map path and overlap scoring weights."""

    parking_map: Path = Path("configs/parking_spaces.example.json")
    footprint_height_ratio: float = Field(default=0.60, gt=0.0, le=1.0)
    candidate_score_threshold: float = Field(default=0.18, ge=0.0, le=1.0)
    occupied_enter_threshold: float = Field(default=0.30, ge=0.0, le=1.0)
    occupied_exit_threshold: float = Field(default=0.12, ge=0.0, le=1.0)
    weight_space_overlap: float = Field(default=0.55, ge=0.0)
    weight_vehicle_overlap: float = Field(default=0.20, ge=0.0)
    weight_center_inside: float = Field(default=0.10, ge=0.0)
    weight_bottom_center_inside: float = Field(default=0.15, ge=0.0)

    @field_validator("occupied_exit_threshold")
    @classmethod
    def _exit_below_enter(cls, value: float, info: object) -> float:
        data = getattr(info, "data", {})
        enter = data.get("occupied_enter_threshold")
        if enter is not None and value >= enter:
            msg = (
                "geometry.occupied_exit_threshold must be lower than "
                f"occupied_enter_threshold ({enter}); got exit={value}."
            )
            raise ValueError(msg)
        return value


class StateSettings(BaseModel):
    """Temporal occupancy confirmation settings."""

    mode: Literal["frames", "seconds"] = "frames"
    enter_confirm_frames: int = Field(default=5, ge=1)
    exit_confirm_frames: int = Field(default=8, ge=1)
    enter_confirm_seconds: float = Field(default=0.5, gt=0.0)
    exit_confirm_seconds: float = Field(default=1.0, gt=0.0)
    unknown_after_invalid_frames: int = Field(default=10, ge=1)


class PersistenceSettings(BaseModel):
    """SQLite / event retention settings."""

    database_url: str = "sqlite:///output/parking.db"
    snapshot_interval_seconds: float = Field(default=5.0, gt=0.0)
    event_retention_days: int = Field(default=90, ge=1)


class ApiSettings(BaseModel):
    """HTTP API bind settings."""

    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)


class Settings(BaseModel):
    """Root application settings assembled from layered sources."""

    app: AppSettings = Field(default_factory=AppSettings)
    camera: CameraSettings = Field(default_factory=CameraSettings)
    video: VideoSettings = Field(default_factory=VideoSettings)
    model: ModelSettings = Field(default_factory=ModelSettings)
    geometry: GeometrySettings = Field(default_factory=GeometrySettings)
    state: StateSettings = Field(default_factory=StateSettings)
    persistence: PersistenceSettings = Field(default_factory=PersistenceSettings)
    api: ApiSettings = Field(default_factory=ApiSettings)

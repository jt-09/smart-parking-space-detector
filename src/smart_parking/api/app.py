"""FastAPI application factory."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from smart_parking import __version__
from smart_parking.api.routes import api_router, router
from smart_parking.api.runtime import AppContext, StatusStore, source_status_from_settings
from smart_parking.config.models import Settings
from smart_parking.domain.state import OccupancySnapshot
from smart_parking.persistence.repository import EventRepository

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


def create_app(
    *,
    settings: Settings | None = None,
    store: StatusStore | None = None,
    repository: EventRepository | None = None,
    snapshot: OccupancySnapshot | None = None,
) -> FastAPI:
    """Build the FastAPI application with injectable status and repository state.

    Tests and the ``serve`` CLI both call this factory. Snapshot/repository
    injection avoids requiring a live camera or YOLO weights.
    """
    resolved_settings = settings if settings is not None else Settings()
    resolved_store = store
    if resolved_store is None:
        resolved_store = StatusStore(source=source_status_from_settings(resolved_settings))
    if snapshot is not None:
        resolved_store.set_snapshot(snapshot)

    context = AppContext(
        settings=resolved_settings,
        store=resolved_store,
        repository=repository,
    )

    app = FastAPI(
        title="Smart Parking-Space Detector API",
        version=__version__,
        description=(
            "Status and analytics API for fixed-camera parking occupancy. "
            "Default bind is localhost (127.0.0.1:8000)."
        ),
    )
    app.state.context = context
    app.include_router(router)
    app.include_router(api_router)

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def dashboard(request: Request) -> HTMLResponse:
        from smart_parking.api.routes import _source_response, _space_response

        snap = resolved_store.get_snapshot()
        source = _source_response(resolved_store)
        spaces = [_space_response(s) for s in snap.spaces] if snap is not None else []
        events: list[object] = []
        if repository is not None:
            events = list(reversed(repository.list_events(limit=15)))

        available = snap.available if snap is not None else 0
        occupied = snap.occupied if snap is not None else 0
        unknown = snap.unknown if snap is not None else 0
        total = len(snap.spaces) if snap is not None else 0
        occupancy_percent = snap.occupancy_percent if snap is not None else 0.0

        return templates.TemplateResponse(
            request,
            "dashboard.html",
            {
                "title": "Smart Parking Status",
                "version": __version__,
                "camera_id": resolved_settings.camera.id,
                "captured_at": snap.captured_at if snap is not None else None,
                "total": total,
                "available": available,
                "occupied": occupied,
                "unknown": unknown,
                "occupancy_percent": occupancy_percent,
                "stale": source.stale,
                "source": source,
                "spaces": spaces,
                "events": events,
                "persistence_enabled": repository is not None,
            },
        )

    return app

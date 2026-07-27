"""API contract tests using FastAPI TestClient (no camera / YOLO weights)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from smart_parking.api.app import create_app
from smart_parking.api.runtime import StatusStore, empty_snapshot, source_status_from_settings
from smart_parking.config.models import Settings
from smart_parking.domain.events import EventType, OccupancyEvent
from smart_parking.domain.state import OccupancySnapshot, OccupancyState, SpaceOccupancy
from smart_parking.persistence.db import create_db_engine, init_schema, make_session_factory
from smart_parking.persistence.repository import SqlAlchemyEventRepository


@pytest.fixture
def settings() -> Settings:
    return Settings()


@pytest.fixture
def snapshot() -> OccupancySnapshot:
    now = datetime(2026, 7, 27, 12, 0, 0, tzinfo=UTC)
    return OccupancySnapshot(
        camera_id="lot-a-camera-01",
        captured_at=now,
        run_id=str(uuid4()),
        spaces=(
            SpaceOccupancy("A1", OccupancyState.AVAILABLE, confidence=0.91),
            SpaceOccupancy("A2", OccupancyState.OCCUPIED, confidence=0.88, track_id="t-1"),
            SpaceOccupancy("A3", OccupancyState.UNKNOWN, confidence=0.10),
            SpaceOccupancy("A4", OccupancyState.PENDING_OCCUPIED, confidence=0.40),
        ),
    )


@pytest.fixture
def repository(tmp_path: Path) -> SqlAlchemyEventRepository:
    url = f"sqlite:///{tmp_path / 'api.db'}"
    engine = create_db_engine(url)
    init_schema(engine)
    return SqlAlchemyEventRepository(make_session_factory(engine))


def _build_client(
    *,
    settings: Settings,
    snapshot: OccupancySnapshot | None,
    repository: SqlAlchemyEventRepository | None,
    last_frame_at: datetime | None = None,
) -> TestClient:
    store = StatusStore(source=source_status_from_settings(settings))
    if last_frame_at is not None:
        store.source.last_frame_at = last_frame_at
    app = create_app(settings=settings, store=store, repository=repository, snapshot=snapshot)
    return TestClient(app)


def test_health_endpoints(settings: Settings, snapshot: OccupancySnapshot) -> None:
    client = _build_client(settings=settings, snapshot=snapshot, repository=None)
    for path in ("/health", "/api/v1/health"):
        response = client.get(path)
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert "version" in payload


def test_openapi_docs_load(settings: Settings, snapshot: OccupancySnapshot) -> None:
    client = _build_client(settings=settings, snapshot=snapshot, repository=None)
    docs = client.get("/docs")
    assert docs.status_code == 200
    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200
    schema = openapi.json()
    paths = schema["paths"]
    assert "/api/v1/status" in paths
    assert "/api/v1/spaces" in paths
    assert "/api/v1/events" in paths
    assert "/api/v1/analytics/occupancy" in paths
    assert "/api/v1/analytics/turnover" in paths
    assert "/api/v1/runs" in paths


def test_status_and_spaces(settings: Settings, snapshot: OccupancySnapshot) -> None:
    client = _build_client(settings=settings, snapshot=snapshot, repository=None)
    status = client.get("/api/v1/status")
    assert status.status_code == 200
    body = status.json()
    assert body["total_spaces"] == 4
    assert body["available"] == 1
    assert body["occupied"] == 1
    assert body["unknown"] == 2
    assert body["occupancy_percent"] == pytest.approx(50.0)
    assert body["stale"] is True

    spaces = client.get("/api/v1/spaces")
    assert spaces.status_code == 200
    rows = spaces.json()
    assert len(rows) == 4
    pending = next(r for r in rows if r["space_id"] == "A4")
    assert pending["state"] == "unknown"
    assert pending["is_pending"] is True
    assert pending["is_unknown"] is True

    one = client.get("/api/v1/spaces/A2")
    assert one.status_code == 200
    assert one.json()["state"] == "occupied"

    missing = client.get("/api/v1/spaces/ZZZ")
    assert missing.status_code == 404
    assert "ZZZ" in missing.json()["detail"]


def test_status_without_snapshot(settings: Settings) -> None:
    client = _build_client(settings=settings, snapshot=None, repository=None)
    status = client.get("/api/v1/status").json()
    assert status["stale"] is True
    assert status["total_spaces"] == 0
    assert status["captured_at"] is None
    assert client.get("/api/v1/spaces").json() == []


def test_events_analytics_and_runs(
    settings: Settings,
    snapshot: OccupancySnapshot,
    repository: SqlAlchemyEventRepository,
) -> None:
    run_id = snapshot.run_id or str(uuid4())
    run_uuid = UUID(run_id)
    started = datetime(2026, 7, 27, 11, 0, 0, tzinfo=UTC)
    repository.start_run(
        run_id=run_id,
        camera_id=snapshot.camera_id,
        source_fingerprint="synthetic",
        started_at=started,
        model_name="fake",
    )
    occupied_at = started + timedelta(minutes=5)
    vacated_at = started + timedelta(minutes=25)
    repository.persist_event(
        OccupancyEvent(
            id=uuid4(),
            run_id=run_uuid,
            space_id="A2",
            event_type=EventType.OCCUPIED,
            previous_state=OccupancyState.AVAILABLE,
            new_state=OccupancyState.OCCUPIED,
            confirmed_at=occupied_at,
            confidence=0.9,
            idempotency_key=f"{run_id}:A2:occupied",
        )
    )
    repository.persist_event(
        OccupancyEvent(
            id=uuid4(),
            run_id=run_uuid,
            space_id="A2",
            event_type=EventType.VACATED,
            previous_state=OccupancyState.OCCUPIED,
            new_state=OccupancyState.AVAILABLE,
            confirmed_at=vacated_at,
            confidence=0.85,
            idempotency_key=f"{run_id}:A2:vacated",
        )
    )
    repository.complete_run(
        run_id,
        ended_at=started + timedelta(hours=1),
        frames_read=100,
        frames_processed=50,
    )

    client = _build_client(settings=settings, snapshot=snapshot, repository=repository)

    events = client.get(
        "/api/v1/events",
        params={
            "limit": 10,
            "space_id": "A2",
            "run_id": run_id,
            "after": occupied_at.isoformat(),
            "before": (vacated_at + timedelta(seconds=1)).isoformat(),
        },
    )
    assert events.status_code == 200
    payload = events.json()
    assert payload["count"] == 2
    assert payload["events"][0]["event_type"] == "vacated"

    occupancy = client.get(
        "/api/v1/analytics/occupancy",
        params={"space_id": "A2", "after": started.isoformat()},
    )
    assert occupancy.status_code == 200
    occ = occupancy.json()
    assert occ["completed_stays"] == 1
    assert occ["mean_duration_seconds"] == pytest.approx(20 * 60)
    assert len(occ["buckets"]) >= 1

    turnover = client.get("/api/v1/analytics/turnover", params={"space_id": "A2"})
    assert turnover.status_code == 200
    turn = turnover.json()
    assert turn["occupied_count"] == 1
    assert turn["vacated_count"] == 1

    runs = client.get("/api/v1/runs", params={"limit": 5})
    assert runs.status_code == 200
    assert runs.json()["count"] == 1
    assert runs.json()["runs"][0]["id"] == run_id

    one_run = client.get(f"/api/v1/runs/{run_id}")
    assert one_run.status_code == 200
    assert one_run.json()["status"] == "completed"

    missing_run = client.get("/api/v1/runs/does-not-exist")
    assert missing_run.status_code == 404


def test_invalid_query_params_return_structured_errors(
    settings: Settings,
    snapshot: OccupancySnapshot,
    repository: SqlAlchemyEventRepository,
) -> None:
    client = _build_client(settings=settings, snapshot=snapshot, repository=repository)

    bad_limit = client.get("/api/v1/events", params={"limit": 0})
    assert bad_limit.status_code == 422
    assert "detail" in bad_limit.json()

    bad_after = client.get("/api/v1/events", params={"after": "not-a-date"})
    assert bad_after.status_code == 422
    body = bad_after.json()
    assert "detail" in body
    assert "after" in str(body["detail"]).lower() or "ISO-8601" in str(body["detail"])

    empty_after = client.get("/api/v1/events", params={"after": "   "})
    assert empty_after.status_code == 422

    zulu = client.get("/api/v1/analytics/turnover", params={"before": "2026-07-27T12:00:00Z"})
    assert zulu.status_code == 200


def test_events_without_repository_returns_503(
    settings: Settings,
    snapshot: OccupancySnapshot,
) -> None:
    client = _build_client(settings=settings, snapshot=snapshot, repository=None)
    response = client.get("/api/v1/events")
    assert response.status_code == 503
    assert "persistence" in response.json()["detail"].lower()


def test_dashboard_renders_unknown_and_stale(
    settings: Settings,
    snapshot: OccupancySnapshot,
) -> None:
    client = _build_client(settings=settings, snapshot=snapshot, repository=None)
    page = client.get("/")
    assert page.status_code == 200
    text = page.text
    assert "Smart Parking Status" in text
    assert "stale" in text.lower()
    assert "unknown" in text.lower()
    assert "A3" in text
    assert "lot-a-camera-01" in text


def test_dashboard_with_events(
    settings: Settings,
    snapshot: OccupancySnapshot,
    repository: SqlAlchemyEventRepository,
) -> None:
    run_id = snapshot.run_id or str(uuid4())
    repository.start_run(
        run_id=run_id,
        camera_id=snapshot.camera_id,
        source_fingerprint="synthetic",
        started_at=datetime(2026, 7, 27, 11, 0, 0, tzinfo=UTC),
        model_name="fake",
    )
    repository.persist_event(
        OccupancyEvent(
            id=uuid4(),
            run_id=UUID(run_id),
            space_id="A2",
            event_type=EventType.OCCUPIED,
            previous_state=OccupancyState.AVAILABLE,
            new_state=OccupancyState.OCCUPIED,
            confirmed_at=datetime(2026, 7, 27, 11, 5, 0, tzinfo=UTC),
            confidence=0.9,
            idempotency_key=f"{run_id}:A2:occupied:dash",
        )
    )
    client = _build_client(settings=settings, snapshot=snapshot, repository=repository)
    page = client.get("/")
    assert page.status_code == 200
    assert "A2" in page.text
    assert "occupied" in page.text.lower()


def test_fresh_snapshot_not_stale(settings: Settings) -> None:
    now = datetime.now(UTC)
    snap = OccupancySnapshot(
        camera_id=settings.camera.id,
        captured_at=now,
        spaces=(SpaceOccupancy("B1", OccupancyState.AVAILABLE, confidence=1.0),),
    )
    client = _build_client(
        settings=settings,
        snapshot=snap,
        repository=None,
        last_frame_at=now,
    )
    status = client.get("/api/v1/status").json()
    assert status["stale"] is False
    assert status["available"] == 1


def test_empty_snapshot_helper() -> None:
    snap = empty_snapshot(camera_id="cam-x")
    assert snap.camera_id == "cam-x"
    assert snap.spaces == ()
    assert snap.available == 0

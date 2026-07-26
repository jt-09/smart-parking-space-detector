"""Persistence schema, idempotency, analytics, and CLI coverage."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from typer.testing import CliRunner

from smart_parking.cli.main import app
from smart_parking.config.models import (
    AppSettings,
    CameraSettings,
    GeometrySettings,
    PersistenceSettings,
    Settings,
    StateSettings,
    VideoSettings,
)
from smart_parking.detection.fake import FakeDetector
from smart_parking.domain.events import EventType, OccupancyEvent
from smart_parking.domain.parking import ParkingMap, ParkingSpace, Point
from smart_parking.domain.state import OccupancySnapshot, OccupancyState, SpaceOccupancy
from smart_parking.persistence.analytics import (
    calculate_durations,
    calculate_turnover,
    hourly_occupancy_summary,
    mean_duration_seconds,
)
from smart_parking.persistence.db import (
    create_db_engine,
    init_schema,
    make_session_factory,
    migrate,
)
from smart_parking.persistence.events import EventService, TransitionRecorder
from smart_parking.persistence.export import export_events_csv
from smart_parking.persistence.repository import (
    SqlAlchemyEventRepository,
    build_idempotency_key,
)
from smart_parking.pipeline.processor import ParkingProcessor
from smart_parking.sources.synthetic import SyntheticFrameSource


def _space(space_id: str) -> ParkingSpace:
    return ParkingSpace(
        id=space_id,
        label=space_id,
        polygon=(Point(0, 0), Point(10, 0), Point(10, 10), Point(0, 10)),
    )


def _parking_map() -> ParkingMap:
    return ParkingMap(
        camera_id="cam-1",
        reference_width=64,
        reference_height=48,
        spaces=(_space("A1"), _space("A2")),
    )


@pytest.fixture
def repo(tmp_path: Path) -> SqlAlchemyEventRepository:
    url = f"sqlite:///{tmp_path / 'parking.db'}"
    engine = create_db_engine(url)
    init_schema(engine)
    return SqlAlchemyEventRepository(make_session_factory(engine))


def test_migrate_creates_tables(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'm.db'}"
    engine = migrate(url)
    assert engine is not None
    migrate(url)


def test_run_lifecycle_and_space_sync(repo: SqlAlchemyEventRepository) -> None:
    run_id = str(uuid4())
    started = datetime(2026, 7, 26, 18, 0, tzinfo=UTC)
    repo.start_run(
        run_id=run_id,
        camera_id="cam-1",
        source_fingerprint="synthetic",
        started_at=started,
        model_name="fake",
    )
    repo.sync_parking_spaces(_parking_map(), now=started)
    record = repo.get_run(run_id)
    assert record is not None
    assert record.status == "running"

    repo.interrupt_run(
        run_id,
        ended_at=started + timedelta(seconds=5),
        frames_read=10,
        frames_processed=8,
    )
    record = repo.get_run(run_id)
    assert record is not None
    assert record.status == "interrupted"
    assert record.frames_processed == 8


def test_persist_event_idempotent(repo: SqlAlchemyEventRepository) -> None:
    run_id = str(uuid4())
    started = datetime(2026, 7, 26, 18, 10, tzinfo=UTC)
    repo.start_run(
        run_id=run_id,
        camera_id="cam-1",
        source_fingerprint="synthetic",
        started_at=started,
        model_name="fake",
    )
    confirmed = started + timedelta(seconds=2)
    event = OccupancyEvent(
        id=uuid4(),
        run_id=UUID(run_id),
        space_id="A1",
        event_type=EventType.OCCUPIED,
        previous_state=OccupancyState.AVAILABLE,
        new_state=OccupancyState.OCCUPIED,
        confirmed_at=confirmed,
        confidence=0.88,
        idempotency_key=build_idempotency_key(
            run_id=run_id,
            space_id="A1",
            event_type=EventType.OCCUPIED,
            previous_state=OccupancyState.AVAILABLE,
            new_state=OccupancyState.OCCUPIED,
            confirmed_at=confirmed,
        ),
    )
    assert repo.persist_event(event) is True
    assert repo.persist_event(event) is False
    assert len(repo.list_events(run_id=run_id)) == 1


def test_transition_recorder_emits_confirmed_only() -> None:
    run_id = str(uuid4())
    recorder = TransitionRecorder(run_id=run_id)
    t0 = datetime(2026, 7, 26, 19, 0, tzinfo=UTC)

    def snap(state: OccupancyState, *, at: datetime) -> OccupancySnapshot:
        return OccupancySnapshot(
            camera_id="cam-1",
            captured_at=at,
            spaces=(SpaceOccupancy(space_id="A1", state=state, confidence=0.7),),
            frame_index=0,
            run_id=run_id,
        )

    assert recorder.observe(snap(OccupancyState.UNKNOWN, at=t0)) == []
    assert recorder.observe(snap(OccupancyState.PENDING_OCCUPIED, at=t0)) == []
    events = recorder.observe(snap(OccupancyState.OCCUPIED, at=t0 + timedelta(seconds=1)))
    assert len(events) == 1
    assert events[0].event_type == EventType.OCCUPIED
    assert recorder.observe(snap(OccupancyState.OCCUPIED, at=t0 + timedelta(seconds=2))) == []
    vacated = recorder.observe(snap(OccupancyState.AVAILABLE, at=t0 + timedelta(seconds=3)))
    assert len(vacated) == 1
    assert vacated[0].event_type == EventType.VACATED


def test_event_service_dedupes_callbacks(repo: SqlAlchemyEventRepository) -> None:
    run_id = str(uuid4())
    started = datetime(2026, 7, 26, 19, 30, tzinfo=UTC)
    repo.start_run(
        run_id=run_id,
        camera_id="cam-1",
        source_fingerprint="synthetic",
        started_at=started,
        model_name="fake",
    )
    service = EventService(repository=repo, run_id=run_id, snapshot_interval_seconds=60.0)
    snap_unknown = OccupancySnapshot(
        camera_id="cam-1",
        captured_at=started,
        spaces=(SpaceOccupancy(space_id="A1", state=OccupancyState.UNKNOWN, confidence=0.0),),
        run_id=run_id,
    )
    snap_occ = OccupancySnapshot(
        camera_id="cam-1",
        captured_at=started + timedelta(seconds=1),
        spaces=(SpaceOccupancy(space_id="A1", state=OccupancyState.OCCUPIED, confidence=0.9),),
        run_id=run_id,
    )
    service.handle_snapshot(snap_unknown)
    service.handle_snapshot(snap_occ)
    # Replay the same transition (duplicate callback).
    service._recorder = TransitionRecorder(run_id=run_id)
    service._recorder._last_confirmed["A1"] = OccupancyState.UNKNOWN
    service.handle_snapshot(snap_occ)
    assert service.persisted_events == 1
    assert service.duplicate_events == 1
    assert len(repo.list_events(run_id=run_id)) == 1


def test_durations_turnover_and_hourly() -> None:
    run = uuid4()
    t0 = datetime(2026, 7, 26, 20, 0, tzinfo=UTC)
    events = [
        OccupancyEvent(
            id=uuid4(),
            run_id=run,
            space_id="A1",
            event_type=EventType.OCCUPIED,
            previous_state=OccupancyState.AVAILABLE,
            new_state=OccupancyState.OCCUPIED,
            confirmed_at=t0,
            confidence=0.9,
            idempotency_key="k1",
        ),
        OccupancyEvent(
            id=uuid4(),
            run_id=run,
            space_id="A1",
            event_type=EventType.VACATED,
            previous_state=OccupancyState.OCCUPIED,
            new_state=OccupancyState.AVAILABLE,
            confirmed_at=t0 + timedelta(minutes=30),
            confidence=0.8,
            idempotency_key="k2",
        ),
        OccupancyEvent(
            id=uuid4(),
            run_id=run,
            space_id="A1",
            event_type=EventType.OCCUPIED,
            previous_state=OccupancyState.AVAILABLE,
            new_state=OccupancyState.OCCUPIED,
            confirmed_at=t0 + timedelta(hours=1, minutes=5),
            confidence=0.9,
            idempotency_key="k3",
        ),
    ]
    now = t0 + timedelta(hours=1, minutes=20)
    durations = calculate_durations(events, now=now)
    assert len(durations) == 2
    assert durations[0].duration_seconds == pytest.approx(1800.0)
    assert durations[0].still_occupied is False
    assert durations[1].still_occupied is True
    assert durations[1].vacated_at is None
    assert mean_duration_seconds(durations, completed_only=True) == pytest.approx(1800.0)

    turnover = calculate_turnover(events, space_id="A1")
    assert turnover.occupied_count == 2
    assert turnover.vacated_count == 1

    hourly = hourly_occupancy_summary(events)
    assert len(hourly) == 2
    assert hourly[0].occupied_events == 1
    assert hourly[1].occupied_events == 1


def test_purge_and_export(repo: SqlAlchemyEventRepository, tmp_path: Path) -> None:
    run_id = str(uuid4())
    started = datetime(2026, 7, 26, 12, 0, tzinfo=UTC)
    repo.start_run(
        run_id=run_id,
        camera_id="cam-1",
        source_fingerprint="synthetic",
        started_at=started,
        model_name="fake",
    )
    old = OccupancyEvent(
        id=uuid4(),
        run_id=UUID(run_id),
        space_id="A1",
        event_type=EventType.OCCUPIED,
        previous_state=OccupancyState.AVAILABLE,
        new_state=OccupancyState.OCCUPIED,
        confirmed_at=started,
        confidence=0.5,
        idempotency_key="old-key",
    )
    new = OccupancyEvent(
        id=uuid4(),
        run_id=UUID(run_id),
        space_id="A1",
        event_type=EventType.VACATED,
        previous_state=OccupancyState.OCCUPIED,
        new_state=OccupancyState.AVAILABLE,
        confirmed_at=started + timedelta(days=2),
        confidence=0.5,
        idempotency_key="new-key",
    )
    assert repo.persist_event(old)
    assert repo.persist_event(new)
    deleted = repo.purge_before(started + timedelta(days=1))
    assert deleted == 1
    remaining = repo.list_events()
    assert len(remaining) == 1
    out = export_events_csv(remaining, tmp_path / "events.csv")
    text = out.read_text(encoding="utf-8")
    assert "new-key" in text
    assert "old-key" not in text


def test_pipeline_with_persistence(tmp_path: Path) -> None:
    db_path = tmp_path / "pipe.db"
    url = f"sqlite:///{db_path}"
    engine = create_db_engine(url)
    init_schema(engine)
    repository = SqlAlchemyEventRepository(make_session_factory(engine))

    settings = Settings(
        app=AppSettings(environment="test", output_dir=tmp_path / "out"),
        camera=CameraSettings(id="cam-1", source="synthetic"),
        video=VideoSettings(process_every_n_frames=1, save_annotated_video=False),
        geometry=GeometrySettings(
            parking_map=Path("unused.json"),
            candidate_score_threshold=0.10,
            occupied_enter_threshold=0.25,
            occupied_exit_threshold=0.10,
        ),
        state=StateSettings(mode="frames", enter_confirm_frames=2, exit_confirm_frames=2),
        persistence=PersistenceSettings(
            enabled=True, database_url=url, snapshot_interval_seconds=1.0
        ),
    )
    parking = ParkingMap(
        camera_id="cam-1",
        reference_width=64,
        reference_height=48,
        spaces=(
            ParkingSpace(
                id="A1",
                label="A1",
                polygon=(Point(2, 8), Point(30, 8), Point(30, 44), Point(2, 44)),
            ),
        ),
    )
    source = SyntheticFrameSource(
        source_id="cam-1",
        width=64,
        height=48,
        frame_count=12,
        moving_rectangle=True,
    )
    detector = FakeDetector()
    processor = ParkingProcessor(
        settings,
        parking,
        source,
        detector,
        run_id=str(uuid4()),
        event_repository=repository,
    )
    result = processor.run()
    assert not result.interrupted
    run = repository.get_run(result.run_id)
    assert run is not None
    assert run.status == "completed"
    assert run.frames_processed == result.metrics.frames_processed


def test_cli_db_migrate_and_export(tmp_path: Path) -> None:
    db_path = tmp_path / "cli.db"
    url = f"sqlite:///{db_path}"
    runner = CliRunner()
    migrate_result = runner.invoke(app, ["db", "migrate", "--database-url", url])
    assert migrate_result.exit_code == 0, migrate_result.output

    engine = create_db_engine(url)
    repo = SqlAlchemyEventRepository(make_session_factory(engine))
    run_id = str(uuid4())
    started = datetime(2026, 7, 26, 21, 0, tzinfo=UTC)
    repo.start_run(
        run_id=run_id,
        camera_id="cam-1",
        source_fingerprint="x",
        started_at=started,
        model_name="fake",
    )
    event = OccupancyEvent(
        id=uuid4(),
        run_id=UUID(run_id),
        space_id="A1",
        event_type=EventType.OCCUPIED,
        previous_state=OccupancyState.AVAILABLE,
        new_state=OccupancyState.OCCUPIED,
        confirmed_at=started,
        confidence=0.7,
        idempotency_key="cli-key",
    )
    assert repo.persist_event(event)

    out = tmp_path / "events.csv"
    export_result = runner.invoke(
        app,
        ["export-events", "--database-url", url, "--output", str(out), "--format", "csv"],
    )
    assert export_result.exit_code == 0, export_result.output
    assert out.exists()
    assert "cli-key" in out.read_text(encoding="utf-8")

    purge_result = runner.invoke(
        app,
        [
            "db",
            "purge",
            "--database-url",
            url,
            "--before",
            "2026-07-27T00:00:00+00:00",
        ],
    )
    assert purge_result.exit_code == 0, purge_result.output
    assert "Purged 1" in purge_result.output

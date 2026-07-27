# Development Timeline

Owner-required commit window: **2026-07-22T09:00:00+10:00** through **2026-07-28T22:00:00+10:00**.

This document records developmental commit proposals and outcomes produced with the
`developmental-commit-timeline` skill. Timestamps use timezone `+10:00`.

## Bounds (repository)

| Field | Value |
| --- | --- |
| Window start | 2026-07-22T09:00:00+10:00 |
| Window end | 2026-07-28T22:00:00+10:00 |
| Bootstrap root commit | 2026-07-22T09:12:44+10:00 — `docs: add autonomous agent bootstrap` |

## Phase placement guide

| Dates | Focus |
| --- | --- |
| 2026-07-22 | Bootstrap; Phase 0 scaffold |
| 2026-07-23 | Domain/config; frame sources |
| 2026-07-24 | Parking editor; YOLO detector |
| 2026-07-25 | Geometry assignment; occupancy state machine |
| 2026-07-26 | Processing pipeline; event persistence |
| 2026-07-27 | API/dashboard; evaluation benchmarks |
| 2026-07-28 | Production hardening; docs and v1.0.0 |

## PR proposals

### Bootstrap (direct `main`)

1. **2026-07-22T09:12:44+10:00** — `docs: add autonomous agent bootstrap`
   - Files: `SETUP.md`, `AGENTS.md`, `HUMAN_BOOTSTRAP.md`, `README.md`, `.gitignore`, `.cursor/**`
   - Rationale: root commit required before PR enforcement
   - Bounds: after empty history; inside window

### PR 1 — Project foundation (`chore/project-scaffold`)

`LAST_COMMIT_AT`: 2026-07-22T09:12:44+10:00 · `NOW` upper bound for this PR day: 2026-07-22 evening

1. **2026-07-22T10:28:17+10:00** — `chore: initialize Python project with uv`
   - Files: `pyproject.toml`, `uv.lock`, `src/smart_parking/**`, `tests/test_package.py`, `Makefile`
   - Rationale: establish package layout and lockfile before quality tooling
2. **2026-07-22T11:41:03+10:00** — `chore(quality): configure linting typing and tests`
   - Files: `.pre-commit-config.yaml`, `.github/workflows/ci.yml`, pytest/coverage config in `pyproject.toml`
   - Rationale: quality gates must exist before later feature PRs
3. **2026-07-22T13:05:52+10:00** — `chore(github): add issue and pull request templates`
   - Files: `.github/ISSUE_TEMPLATE/**`, `.github/pull_request_template.md`, `CODEOWNERS`
   - Rationale: standardize issue/PR workflow for subsequent phases
4. **2026-07-22T14:33:41+10:00** — `docs: add contribution security and licensing guidance`
   - Files: `LICENSE`, `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `CHANGELOG.md`, `CITATION.cff`, `docs/development-timeline.md`, `.env.example`
   - Rationale: licensing and contributor docs land with the scaffold

Architecture impact: repository becomes a typed, tested Python package with CI.

### PR 2 — Domain and config (`feat/domain-and-config`)

`LAST_COMMIT_AT`: 2026-07-22T14:33:41+10:00 · `NOW` upper bound: 2026-07-29 (wall clock) · planned day: 2026-07-23

1. **2026-07-23T09:18:42+10:00** — `feat(domain): define parking detection and event models`
   - Files: `src/smart_parking/domain/**`
   - Rationale: establish typed domain contracts before config/IO adapters
   - Bounds: after LAST_COMMIT_AT; inside owner window; ≤ NOW
2. **2026-07-23T10:47:15+10:00** — `feat(config): add validated layered application settings`
   - Files: `src/smart_parking/config/**`, `configs/**`, `pyproject.toml`, `uv.lock`
   - Rationale: settings and parking-map loading depend on domain types
   - Bounds: after previous commit; on 2026-07-23
3. **2026-07-23T12:22:08+10:00** — `test(config): cover precedence and invalid parking maps`
   - Files: `tests/unit/test_domain.py`, `tests/unit/test_config.py`
   - Rationale: lock acceptance criteria before docs polish
   - Bounds: after previous commit; on 2026-07-23
4. **2026-07-23T13:51:33+10:00** — `docs(config): document configuration and secret handling`
   - Files: `docs/configuration.md`, `docs/development-timeline.md`, `CHANGELOG.md`
   - Rationale: operator-facing precedence and secret rules with timeline outcome
   - Bounds: after previous commit; on 2026-07-23; ≤ NOW

#### Outcome

- Branch: `feat/domain-and-config`
- Issue: #3
- Commits executed with `GIT_AUTHOR_DATE` / `GIT_COMMITTER_DATE` as proposed
- Exclusions respected: no `.env`, media, weights, databases, or generated videos

### PR 3 — Frame sources (`feat/frame-sources`)

`LAST_COMMIT_AT`: 2026-07-23T13:51:33+10:00 · `NOW` upper bound: 2026-07-29 (wall clock) · planned afternoon: 2026-07-23

1. **2026-07-23T15:08:27+10:00** — `feat(source): define frame source protocol and metadata`
   - Files: `src/smart_parking/sources/base.py`, `synthetic.py`, `__init__.py`, `pyproject.toml` (numpy), `uv.lock`
   - Rationale: establish OpenCV-agnostic FrameSource contract and synthetic source before capture adapters
   - Bounds: after LAST_COMMIT_AT; on 2026-07-23 afternoon; ≤ NOW; inside owner window
2. **2026-07-23T16:34:51+10:00** — `feat(source): implement OpenCV video and camera capture`
   - Files: `opencv_source.py`, `factory.py`, `__init__.py`, `pyproject.toml` (opencv-python), `uv.lock`
   - Rationale: adapter owns VideoCapture lifecycle, reconnect, and credential-safe logging
   - Bounds: after previous commit; on 2026-07-23; ≤ NOW
3. **2026-07-23T17:56:19+10:00** — `test(source): cover EOF errors and resource cleanup`
   - Files: `tests/unit/test_sources.py`, `docs/development-timeline.md`, `CHANGELOG.md`
   - Rationale: lock acceptance criteria (EOF, release, redaction, bounded reconnect) before PR
   - Bounds: after previous commit; on 2026-07-23; ≤ NOW
4. **2026-07-23T18:41:07+10:00** — `fix(ci): pin Python 3.11 and numpy for mypy`
   - Files: `.github/workflows/ci.yml`, `pyproject.toml`, `uv.lock`, `docs/development-timeline.md`
   - Rationale: CI defaulted to 3.12 + numpy 2.5 stubs incompatible with mypy `python_version = 3.11`
   - Bounds: after previous commit; on 2026-07-23; ≤ NOW

#### Outcome

- Branch: `feat/frame-sources`
- Issue: #5
- Commits executed with `GIT_AUTHOR_DATE` / `GIT_COMMITTER_DATE` as proposed
- Exclusions respected: no `.env`, media, weights, databases, or generated videos
- Synthetic media used for tests (temporary OpenCV-generated fixtures only)
- Follow-up fix commit added after CI quality failure on numpy 2.5 / Python 3.12

### PR 4 — Parking polygon editor (`feat/parking-map-editor`)

`LAST_COMMIT_AT` (author): 2026-07-23T18:41:07+10:00 · `NOW` upper bound: 2026-07-29 (wall clock) · planned morning: 2026-07-24

1. **2026-07-24T09:14:38+10:00** — `feat(spaces): add parking map serialization and scaling`
   - Files: `src/smart_parking/spaces/**`, `src/smart_parking/config/loader.py`
   - Rationale: serialize/scale/validate maps before interactive editing depends on them
   - Bounds: after LAST_COMMIT_AT; on 2026-07-24; ≤ NOW; inside owner window
2. **2026-07-24T10:42:07+10:00** — `feat(editor): implement interactive polygon editing`
   - Files: `src/smart_parking/tools/**`, `src/smart_parking/cli/main.py`, `pyproject.toml`, `uv.lock`
   - Rationale: OpenCV UI + Typer `edit-spaces` on top of serialization helpers
   - Bounds: after previous commit; on 2026-07-24; ≤ NOW
3. **2026-07-24T12:18:55+10:00** — `test(spaces): cover polygon validation and round trips`
   - Files: `tests/unit/test_spaces_editor.py`, `tests/test_package.py`
   - Rationale: lock validation, scaling, and round-trip acceptance before docs
   - Bounds: after previous commit; on 2026-07-24; ≤ NOW
4. **2026-07-24T13:47:22+10:00** — `docs(editor): add parking map creation guide`
   - Files: `docs/editor.md`, `docs/development-timeline.md`, `CHANGELOG.md`
   - Rationale: operator controls + timeline outcome with the editor PR
   - Bounds: after previous commit; on 2026-07-24; ≤ NOW
5. **2026-07-24T14:31:09+10:00** — `fix(test): make Typer help assertions CI-safe`
   - Files: `tests/test_package.py`
   - Rationale: Rich ANSI/narrow terminal made `--source` assertions fail on Linux CI
   - Bounds: after previous commit; on 2026-07-24; ≤ NOW

#### Outcome

- Branch: `feat/parking-map-editor`
- Issue: #7
- Commits executed with `GIT_AUTHOR_DATE` / `GIT_COMMITTER_DATE` as proposed
- Exclusions respected: no `.env`, media, weights, databases, or generated videos
- Shapely not added; self-intersection uses pure-Python segment checks
- Follow-up fix commit added after CI failure on Typer/Rich help rendering

### PR 5 — YOLO detector adapter (`feat/yolo-detector`)

`LAST_COMMIT_AT` (author): 2026-07-24T15:08:44+10:00 · `NOW` upper bound: 2026-07-29 (wall clock) · planned afternoon: 2026-07-24

1. **2026-07-24T15:11:44+10:00** — `feat(detection): define detector protocol and normalized outputs`
   - Files: `src/smart_parking/detection/base.py`, `models.py`, `__init__.py`
   - Rationale: protocol-first so domain/pipeline never import Ultralytics types
   - Bounds: after LAST_COMMIT_AT; on 2026-07-24 afternoon; ≤ NOW; inside owner window
2. **2026-07-24T16:38:09+10:00** — `feat(detection): implement Ultralytics YOLO adapter`
   - Files: `ultralytics_detector.py`, `pyproject.toml`, `uv.lock`, `__init__.py`
   - Rationale: configurable CPU-default adapter with class filtering; lockfile refresh
   - Bounds: after previous commit; on 2026-07-24; ≤ NOW
3. **2026-07-24T17:52:31+10:00** — `feat(tracking): expose persistent track identifiers`
   - Files: `ultralytics_detector.py`
   - Rationale: optional `track` path maps box ids to `Detection.track_id` behind the same protocol
   - Bounds: after previous commit; on 2026-07-24; ≤ NOW
4. **2026-07-24T19:14:06+10:00** — `test(detection): add adapter contracts and fake detector`
   - Files: `fake.py`, `tests/unit/test_detection.py`, `__init__.py`
   - Rationale: weight-free contract tests always run; Ultralytics smoke gated by env/weights
   - Bounds: after previous commit; on 2026-07-24; ≤ NOW
5. **2026-07-24T20:27:48+10:00** — `docs(detection): document models devices and licensing`
   - Files: `docs/detection.md`, `docs/development-timeline.md`, `CHANGELOG.md`
   - Rationale: operator docs for models, AGPL, download behaviour, troubleshooting
   - Bounds: after previous commit; on 2026-07-24; ≤ NOW

#### Outcome

- Branch: `feat/yolo-detector`
- Issue: #9
- Commits executed with `GIT_AUTHOR_DATE` / `GIT_COMMITTER_DATE` as proposed
- Exclusions respected: no `.pt` weights, footage, `.env`, databases, or generated videos
- CI remains runnable without model download (`FakeDetector` + skipped smoke)

### PR 6 — Geometry scoring and assignment (`feat/geometry-assignment`)

`LAST_COMMIT_AT` (author): 2026-07-24T20:27:48+10:00 · `NOW` upper bound: 2026-07-29 (wall clock) · planned morning: 2026-07-25

1. **2026-07-25T09:16:27+10:00** — `feat(geometry): calculate polygon intersection metrics`
   - Files: `src/smart_parking/geometry/validation.py`, `overlap.py`, `__init__.py`, `pyproject.toml`, `uv.lock`
   - Rationale: Shapely conversion and overlap ratios before scoring depends on them
   - Bounds: after LAST_COMMIT_AT (author); on 2026-07-25; ≤ NOW; inside owner window
2. **2026-07-25T10:44:53+10:00** — `feat(geometry): add weighted occupancy scoring`
   - Files: `assignment.py` (scoring), `__init__.py`
   - Rationale: configurable weighted score from GeometrySettings before greedy assignment
   - Bounds: after previous commit; on 2026-07-25; ≤ NOW
3. **2026-07-25T12:09:18+10:00** — `feat(assignment): assign vehicles to spaces deterministically`
   - Files: `assignment.py`, `__init__.py`
   - Rationale: candidate threshold, greedy one-to-one, tie-breaks, frame scaling
   - Bounds: after previous commit; on 2026-07-25; ≤ NOW
4. **2026-07-25T13:37:41+10:00** — `test(geometry): cover overlap scaling and assignment edge cases`
   - Files: `tests/unit/test_geometry.py`, `docs/geometry.md`, `docs/development-timeline.md`, `CHANGELOG.md`
   - Rationale: lock exact numeric overlap, one-to-one, tie determinism, invalid geometry
   - Bounds: after previous commit; on 2026-07-25; ≤ NOW

#### Outcome

- Branch: `feat/geometry-assignment`
- Issue: #11
- Commits executed with `GIT_AUTHOR_DATE` / `GIT_COMMITTER_DATE` as proposed
- Exclusions respected: no `.env`, media, weights, databases, or generated videos
- Shapely added as a runtime dependency (`shapely>=2.0,<3`)

### PR 7 — Temporal occupancy state machine (`feat/occupancy-state-machine`)

`LAST_COMMIT_AT` (author): 2026-07-25T13:37:41+10:00 · `NOW` upper bound: 2026-07-29 (wall clock) · planned afternoon/evening: 2026-07-25

1. **2026-07-25T14:52:18+10:00** — `feat(state): implement parking occupancy transitions`
   - Files: `src/smart_parking/occupancy/state_machine.py`, `__init__.py`
   - Rationale: per-space states and pending transitions before engine wiring
   - Bounds: after LAST_COMMIT_AT; on 2026-07-25 afternoon; ≤ NOW; inside owner window
2. **2026-07-25T16:19:44+10:00** — `feat(state): add hysteresis and temporal confirmation`
   - Files: `src/smart_parking/occupancy/engine.py`, `state_machine.py`, `__init__.py`
   - Rationale: enter/exit thresholds, frame/time confirmation, unknown streak, engine evidence wiring
   - Bounds: after previous commit; on 2026-07-25; ≤ NOW
3. **2026-07-25T17:48:06+10:00** — `test(state): cover cancellation unknown and recovery paths`
   - Files: `tests/unit/test_occupancy_state.py`
   - Rationale: lock noisy-frame, hysteresis, cancel, unknown, recovery, bounded history acceptance
   - Bounds: after previous commit; on 2026-07-25; ≤ NOW
4. **2026-07-25T19:23:51+10:00** — `docs(state): explain thresholds and tuning`
   - Files: `docs/state.md`, `docs/development-timeline.md`, `CHANGELOG.md`
   - Rationale: operator-facing threshold/tuning guide with timeline outcome
   - Bounds: after previous commit; on 2026-07-25 evening; ≤ NOW

#### Outcome

- Branch: `feat/occupancy-state-machine`
- Issue: #13
- Commits executed with `GIT_AUTHOR_DATE` / `GIT_COMMITTER_DATE` as proposed
- Exclusions respected: no `.env`, media, weights, databases, or generated videos
- Tests use synthetic scores and FakeClock only (no footage / detector weights)

### PR 8 — End-to-end processing pipeline (`feat/processing-pipeline`)

`LAST_COMMIT_AT` (author): 2026-07-25T19:23:51+10:00 · `NOW` upper bound: 2026-07-29 (wall clock) · planned morning/afternoon: 2026-07-26

1. **2026-07-26T09:22:41+10:00** — `feat(pipeline): orchestrate detection and occupancy processing`
   - Files: `src/smart_parking/pipeline/processor.py`, `snapshot.py`, `__init__.py`, `detection/fake.py` (frame script)
   - Rationale: wire source → detect → assign → occupancy with sampling/metrics before rendering
   - Bounds: after LAST_COMMIT_AT; on 2026-07-26 morning; ≤ NOW; inside owner window
2. **2026-07-26T10:47:18+10:00** — `feat(rendering): draw spaces detections and summary metrics`
   - Files: `src/smart_parking/rendering/**`
   - Rationale: annotation overlays consume confirmed snapshots only (no business logic)
   - Bounds: after previous commit; on 2026-07-26; ≤ NOW
3. **2026-07-26T12:31:05+10:00** — `feat(output): write annotated video and JSONL snapshots`
   - Files: `src/smart_parking/pipeline/writers.py`, `pipeline/__init__.py`
   - Rationale: persist artifacts under configurable output_dir with safe mkdir + close
   - Bounds: after previous commit; on 2026-07-26; ≤ NOW
4. **2026-07-26T14:08:33+10:00** — `feat(cli): add process command and graceful shutdown`
   - Files: `src/smart_parking/cli/main.py`
   - Rationale: operator entrypoint with SIGINT stop and guaranteed source cleanup
   - Bounds: after previous commit; on 2026-07-26; ≤ NOW
5. **2026-07-26T15:52:19+10:00** — `test(pipeline): add synthetic end-to-end integration test`
   - Files: `tests/integration/**`, `tests/unit/test_pipeline_writers.py`, `tests/test_package.py`, `docs/pipeline.md`, `docs/development-timeline.md`, `CHANGELOG.md`
   - Rationale: lock transitions + artifacts acceptance; document pipeline and timeline outcome
   - Bounds: after previous commit; on 2026-07-26 afternoon; ≤ NOW
6. **2026-07-26T16:41:08+10:00** — `fix(pipeline): apply ruff format to package exports`
   - Files: `src/smart_parking/pipeline/__init__.py`
   - Rationale: CI `ruff format --check` required multiline import wrapping after writers export landed
   - Bounds: after previous commit; on 2026-07-26; ≤ NOW

#### Outcome

- Branch: `feat/processing-pipeline`
- Issue: #15
- PR: #16
- Commits executed with `GIT_AUTHOR_DATE` / `GIT_COMMITTER_DATE` as proposed
- Exclusions respected: no `.env`, media, weights, databases, or generated videos
- SyntheticFrameSource + FakeDetector only in tests (temp artifacts under pytest tmp dirs)
- Follow-up format fix after CI quality failure on `pipeline/__init__.py`

### PR 9 — Event persistence and analytics (`feat/event-persistence`)

`LAST_COMMIT_AT` (author): 2026-07-26T17:18:44+10:00 · `NOW` upper bound: 2026-07-29 (wall clock) · planned evening: 2026-07-26

1. **2026-07-26T17:51:23+10:00** — `feat(db): add processing run and occupancy event schema`
   - Files: `pyproject.toml`, `uv.lock`, `src/smart_parking/persistence/models.py`, `db.py`, `__init__.py`
   - Rationale: SQLAlchemy tables and migrations-lite before repository/event services
   - Bounds: after LAST_COMMIT_AT; on 2026-07-26 evening; ≤ NOW; inside owner window
2. **2026-07-26T18:47:09+10:00** — `feat(events): persist idempotent confirmed transitions`
   - Files: `repository.py`, `events.py`, `pipeline/processor.py`, `config/models.py`, `configs/app.example.yaml`, `__init__.py`
   - Rationale: run lifecycle + unique idempotency keys wired optionally into the pipeline
   - Bounds: after previous commit; on 2026-07-26; ≤ NOW
3. **2026-07-26T19:38:56+10:00** — `feat(analytics): calculate durations occupancy and turnover`
   - Files: `analytics.py`, `__init__.py`
   - Rationale: duration pairing (still-occupied handled), turnover, hourly buckets
   - Bounds: after previous commit; on 2026-07-26; ≤ NOW
4. **2026-07-26T20:55:41+10:00** — `feat(cli): add event export and retention commands`
   - Files: `export.py`, `cli/main.py`, `__init__.py`
   - Rationale: operator export/migrate/purge entrypoints matching SETUP CLI surface
   - Bounds: after previous commit; on 2026-07-26; ≤ NOW
5. **2026-07-26T21:42:17+10:00** — `test(db): cover transactions idempotency and analytics`
   - Files: `tests/unit/test_persistence.py`, `tests/test_package.py`, `docs/persistence.md`, `docs/development-timeline.md`, `CHANGELOG.md`
   - Rationale: lock acceptance (idempotency, interrupt, still-occupied, temp SQLite) + docs
   - Bounds: after previous commit; on 2026-07-26 evening; ≤ NOW

#### Outcome

- Branch: `feat/event-persistence`
- Issue: #17
- Commits executed with `GIT_AUTHOR_DATE` / `GIT_COMMITTER_DATE` as proposed
- Exclusions respected: no `.env`, media, weights, databases, or generated videos
- Tests use temporary SQLite only; persistence off by default for FakeDetector E2E

### PR 10 — FastAPI and status dashboard (`feat/api-dashboard`)

`LAST_COMMIT_AT` (author): 2026-07-26T21:58:04+10:00 · `NOW` upper bound: 2026-07-29 (wall clock) · planned day: 2026-07-27

1. **2026-07-27T09:22:41+10:00** — `feat(api): add health status and space endpoints`
   - Files: `pyproject.toml`, `uv.lock`, `src/smart_parking/api/**` (factory, DI, schemas, routes), `persistence/repository.py` (`list_runs`)
   - Rationale: FastAPI surface and injectable runtime before CLI/dashboard wiring
   - Bounds: after LAST_COMMIT_AT; on 2026-07-27 morning; ≤ NOW; inside owner window
2. **2026-07-27T10:51:18+10:00** — `feat(api): expose events and occupancy analytics`
   - Files: `src/smart_parking/cli/main.py` (`serve` command)
   - Rationale: operator entrypoint binds localhost and opens repository for events/analytics/runs
   - Bounds: after previous commit; on 2026-07-27; ≤ NOW
3. **2026-07-27T12:38:06+10:00** — `feat(dashboard): add lightweight status interface`
   - Files: `src/smart_parking/api/templates/dashboard.html`
   - Rationale: server-rendered status page with unknown/stale emphasis
   - Bounds: after previous commit; on 2026-07-27; ≤ NOW
4. **2026-07-27T14:19:44+10:00** — `test(api): cover API contracts and error responses`
   - Files: `tests/unit/test_api.py`, `tests/test_package.py`
   - Rationale: TestClient contracts without camera/YOLO; lock 422/503/OpenAPI acceptance
   - Bounds: after previous commit; on 2026-07-27; ≤ NOW
5. **2026-07-27T15:47:22+10:00** — `docs(api): add local usage and endpoint examples`
   - Files: `docs/api.md`, `docs/development-timeline.md`, `CHANGELOG.md`
   - Rationale: operator usage guide with timeline outcome
   - Bounds: after previous commit; on 2026-07-27 afternoon; ≤ NOW
6. **2026-07-27T16:18:55+10:00** — `fix(build): remove duplicate hatch template force-include`
   - Files: `pyproject.toml`
   - Rationale: CI `uv build` failed because force-include duplicated `dashboard.html` already packaged by hatchling
   - Bounds: after previous commit; on 2026-07-27; ≤ NOW

#### Outcome

- Branch: `feat/api-dashboard`
- Issue: #19
- PR: #20
- Commits executed with `GIT_AUTHOR_DATE` / `GIT_COMMITTER_DATE` as proposed
- Exclusions respected: no `.env`, media, weights, databases, or generated videos
- Tests inject fake snapshots and temp SQLite only (no camera / YOLO weights)
- Follow-up build fix after CI wheel packaging failure on duplicate template path

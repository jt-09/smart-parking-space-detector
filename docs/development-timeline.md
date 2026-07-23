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

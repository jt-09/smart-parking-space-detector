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

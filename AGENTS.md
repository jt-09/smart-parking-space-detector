# Smart Parking Agent Instructions

## Required reading

Before making any change, read `SETUP.md` in full. Treat it as the source of truth. Read `HUMAN_BOOTSTRAP.md` for the owner-created environment and remote constraints.

## Mission

Implement the complete Smart Parking-Space Detector from Phase 0 through the `v1.0.0` release. Work one issue and one reviewable PR at a time. Continue between phases without waiting for routine confirmation.

## Developmental commit timeline (owner-required)

This repository uses the installed **developmental-commit-timeline** skill for every implementation PR.

| Field | Value |
| --- | --- |
| Skill | `developmental-commit-timeline` |
| Commit window start | `2026-07-22T09:00:00+10:00` |
| Commit window end | `2026-07-28T22:00:00+10:00` |
| Timezone | `+10:00` (Australia/Brisbane-equivalent offset) |
| Style | Conventional Commits, developmental milestones |

### Mandatory rules

- Invoke the skill **before the first implementation commit** and **at every PR boundary**.
- Plan and execute commits only inside the July 22–28 window above.
- Produce a written **commit proposal** (timestamp, message, file scope, rationale, bounds check) before executing each PR's commits.
- Persist proposals and outcomes in `docs/development-timeline.md` and in each PR body's `Development timeline` subsection.
- Use `GIT_AUTHOR_DATE` and `GIT_COMMITTER_DATE` for each planned timestamp.
- Keep author identity as the authenticated repository owner. Do not invent collaborators or fake review identities.
- Never schedule timestamps in the future relative to wall-clock `NOW`, and never before the previous commit on the branch.
- Never commit secrets, footage, datasets, model weights, databases, or generated output media.

### Phase placement across the window (planning guide)

Distribute genuine incremental work across the window. Exact timestamps come from each PR's skill proposal.

| Dates | Focus |
| --- | --- |
| 2026-07-22 | Bootstrap root commit; Phase 0 scaffold PR |
| 2026-07-23 | Domain/config; frame sources |
| 2026-07-24 | Parking editor; YOLO detector |
| 2026-07-25 | Geometry assignment; occupancy state machine |
| 2026-07-26 | Processing pipeline; event persistence |
| 2026-07-27 | API/dashboard; evaluation benchmarks |
| 2026-07-28 | Production hardening; docs and v1.0.0 release prep |

## Git and GitHub rules

- Never push feature work directly to `main`.
- Use the exact phase, issue, branch, PR, test, and acceptance sequence in `SETUP.md`.
- Discover and invoke the installed developmental commit timeline skill before the first implementation commit and at every PR boundary.
- Run local checks before pushing and wait for GitHub checks before merging.
- Perform a separate review pass before each merge. Do not describe self-review or Bugbot as independent human approval.
- Use rebase merge and delete the merged branch.
- If GitHub MCP lacks an operation, use authenticated `gh`. If both are unavailable, complete local work and write the exact blocked operation and owner command into `docs/blocked-remote-operations.md`.

## Execution defaults

- Python 3.11 managed by `uv`; do not hand-create or activate a virtual environment.
- Fixed-camera MVP with manually configured polygons.
- Use deterministic synthetic media for tests and the default demo.
- Real footage is optional and must never be committed.
- CPU compatibility is required; GPU acceleration is optional.
- No secrets are needed for the application.
- Do not commit YOLO weights, footage, `.env`, SQLite files, output media, caches, or generated build artifacts.

## Quality gates

Never merge with failing, pending, missing, or bypassed required checks. Do not reduce coverage, thresholds, typing, lint, security, or acceptance criteria merely to obtain green CI.

## Stop only for hard blockers

Stop merging only for an unresolved license conflict, leaked credential, unlicensed/private footage, impossible repository permission, or a required acceptance target that cannot be met without changing scope or making an unsupported claim. Continue all unaffected local work and report the blocker precisely.

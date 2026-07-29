# Dataset and privacy

Media, labels, and privacy rules for Smart Parking-Space Detector.

## Default: synthetic media

CI, smoke tests, and the documented quick start use **deterministic synthetic
frames** plus `FakeDetector`. That path:

- does not download YOLO weights;
- does not require private parking-lot footage;
- is safe to commit as code/fixtures (not as large generated videos).

Generate demos locally under `output/` and keep them untracked.

## Real footage (optional, never committed)

A licensed fixed-camera clip may be used for portfolio demos **outside** the
repository. Rules:

1. Confirm you have rights to use and publish the clip.
2. Store footage outside the repo (local disk or private storage).
3. Never commit videos, frame dumps, databases, or annotated outputs.
4. Prefer clips without readable license plates or faces when possible; if they
   appear, treat the media as sensitive and avoid public redistribution.
5. Document any published evaluation with camera, model, thresholds, hardware,
   and clip identity — without uploading the clip to GitHub.

`.gitignore` already excludes common media, weight, database, and output paths.

## Evaluation labels

Example ground-truth / prediction CSVs under `docs/assets/` are **toy fixtures**
for metric math and docs. They are not a production dataset.

When building a private evaluation set:

- Keep labels next to the private media (not in git).
- Use the schema in [`evaluation.md`](evaluation.md).
- Do not invent “90%+ on real footage” claims without that set.

## Personally identifying information

This project does **not** perform face recognition, license-plate recognition,
or person identification. Operators remain responsible for:

- camera placement and signage where legally required;
- retention of any recorded video or SQLite event history;
- redacting credentials from logs (built-in helpers strip RTSP userinfo);
- not committing `.env` files or raw connection strings.

## Secrets and credentials

| Allowed in repo | Never commit |
| --- | --- |
| `.env.example` (names only) | `.env` with real values |
| Example YAML / parking maps | RTSP passwords, API tokens |
| Synthetic fixtures | Model weights (`*.pt`), SQLite DBs, footage |

See [`SECURITY.md`](../SECURITY.md) and [`configuration.md`](configuration.md).

## Licensing reminder

- Application license: **AGPL-3.0**.
- Default YOLO stack (Ultralytics): **AGPL-3.0** for open-source use; commercial
  redistribution needs separate review.
- Third-party media remains under its own license — the AGPL does not grant you
  rights to other people’s footage.

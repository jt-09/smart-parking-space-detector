# Event persistence

SQLite persistence for processing runs, confirmed occupancy transitions, and
optional interval snapshots. Persistence is **off by default** so FakeDetector
end-to-end runs stay weight-free and database-free unless opted in.

## Enable

```yaml
persistence:
  enabled: true
  database_url: sqlite:///output/parking.db
  snapshot_interval_seconds: 5
  event_retention_days: 90
```

Or at the CLI:

```bash
smart-parking process --persist --database-url sqlite:///output/parking.db ...
smart-parking db migrate --database-url sqlite:///output/parking.db
smart-parking export-events --format csv --output output/events.csv
smart-parking db purge --before 2026-01-01T00:00:00+00:00
```

`*.db` files under `output/` are gitignored. Tests use temporary SQLite URLs only.

## Tables

| Table | Purpose |
| --- | --- |
| `processing_runs` | Run lifecycle (`running` / `completed` / `failed` / `interrupted`) |
| `parking_spaces` | Optional sync of the configured map |
| `occupancy_events` | Confirmed transitions with unique `idempotency_key` |
| `occupancy_snapshots` | Interval aggregate counts (not every frame) |

Schema creation is migrations-lite: `create_all` via `smart-parking db migrate`.

## Idempotency

Duplicate pipeline callbacks that replay the same confirmed transition share the
same `idempotency_key`. The unique constraint rejects the second insert; the
repository returns `False` instead of raising.

Only confirmed states (`available`, `occupied`, `unknown`) produce events.
Pending states are ignored until they resolve. `VACATED` is emitted only when
leaving `occupied` for `available`.

## Analytics

Helpers in `smart_parking.persistence.analytics`:

- **Durations** — pair `OCCUPIED` → `VACATED`; still-occupied stays use `now`
  and set `still_occupied=True` with `vacated_at=None`.
- **Turnover** — occupied / vacated / unknown event counts.
- **Hourly summary** — UTC hour buckets of those counts.

## Pipeline wiring

Inject an `EventRepository` into `ParkingProcessor` (or enable
`persistence.enabled` in the process CLI). When absent, the pipeline behaves
exactly as before.

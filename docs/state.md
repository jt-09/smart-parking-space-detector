# Occupancy state machine

Raw geometry scores are noisy. The occupancy state machine converts per-frame
evidence into stable parking-space states using hysteresis and temporal
confirmation (SETUP §5.7).

## States

| State | Meaning |
| --- | --- |
| `unknown` | No reliable observation yet, or source/quality failure |
| `available` | Confirmed empty |
| `occupied` | Confirmed occupied |
| `pending_occupied` | Entering occupancy; waiting for confirmation |
| `pending_available` | Leaving occupancy; waiting for confirmation |

Machines start in `unknown`. Valid frames with sustained low or high evidence
recover into `available` or `occupied`.

## Hysteresis thresholds

Enter and exit use **different** score thresholds from `GeometrySettings`:

| Setting | Default | Role |
| --- | --- | --- |
| `geometry.occupied_enter_threshold` | `0.30` | Minimum score to begin / sustain enter |
| `geometry.occupied_exit_threshold` | `0.12` | Maximum score to begin / sustain exit |

Scores between the exit and enter thresholds sit in a dead band: an available
space stays available, an occupied space stays occupied. That gap is the
hysteresis that suppresses flicker when a box barely overlaps a polygon.

Configuration validates that exit is strictly lower than enter.

## Temporal confirmation

`StateSettings.mode` selects how long evidence must persist:

| Mode | Enter | Exit |
| --- | --- | --- |
| `frames` (default) | `enter_confirm_frames` (5) | `exit_confirm_frames` (8) |
| `seconds` | `enter_confirm_seconds` (0.5) | `exit_confirm_seconds` (1.0) |

Exit confirmation is deliberately longer than enter so brief detection dropouts
do not vacate a space. With default frame settings, **one noisy high-score
frame cannot confirm occupancy** — it only moves the space into
`pending_occupied`, and falling evidence cancels back to `available`.

Time-based mode is preferred for variable-FPS streams. Pass an injectable UTC
`Clock` (or `observed_at`) so tests freeze time without monkeypatching.

## Unknown and recovery

Consecutive invalid frames (source disconnect, quality failure, detector error)
increment a streak. After `state.unknown_after_invalid_frames` (default `10`),
the space becomes `unknown` regardless of the previous confirmed state.

Recovery from `unknown` requires the same confirmation budget as an enter:

- sustained score ≥ enter threshold → `occupied`
- sustained score < enter threshold → `available`

Flipping between high and low evidence while unknown resets the recovery
counter so mixed noise cannot confirm the wrong state.

## Evidence history and confidence

Each update appends an `EvidenceSample` to a bounded deque
(`DEFAULT_EVIDENCE_HISTORY_MAXLEN = 64`, overridable per machine/engine).
History never grows without bound. Confidence is derived from the latest score
and lowered while a transition is still pending.

## Engine wiring

`OccupancyEngine` owns one `OccupancyStateMachine` per enabled space. Feed it:

- a mapping of `space_id → score`,
- a sequence of `SpaceEvidence`, or
- geometry `SpaceAssignment` results via `update_assignments`.

Unassigned spaces receive score `0.0` on valid frames. Set `frame_valid=False`
for the whole frame when the source or detector is unreliable.

## Tuning tips

1. If spaces flicker occupied/available, widen hysteresis (raise enter and/or
   lower exit) or increase confirm frames/seconds.
2. If occupied updates feel sluggish, reduce `enter_confirm_*` slightly; keep
   exit confirmation longer than enter.
3. If brief camera glitches mark everything unknown, raise
   `unknown_after_invalid_frames`.
4. Prefer `mode: seconds` when `process_every_n_frames` or source FPS varies.
5. Validate changes with synthetic scores (unit tests) before tuning on real
   footage — never commit footage, weights, or generated videos.

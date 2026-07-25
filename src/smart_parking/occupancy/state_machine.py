"""Per-space temporal occupancy state machine (SETUP §5.7).

Raw geometry scores never flip a confirmed state on a single noisy frame.
Enter and exit use separate thresholds (hysteresis). Confirmation is either
frame-count or elapsed-time based, selected by ``StateSettings.mode``.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime

from smart_parking.config.models import GeometrySettings, StateSettings
from smart_parking.domain.state import Clock, OccupancyState, SystemClock

DEFAULT_EVIDENCE_HISTORY_MAXLEN = 64


@dataclass(frozen=True, slots=True)
class EvidenceSample:
    """One frame of occupancy evidence for a parking space."""

    score: float
    valid: bool
    observed_at: datetime
    track_id: str | None = None


@dataclass(slots=True)
class SpaceRuntimeState:
    """Mutable runtime bookkeeping for one parking space."""

    space_id: str
    state: OccupancyState = OccupancyState.UNKNOWN
    confidence: float = 0.0
    last_score: float = 0.0
    track_id: str | None = None
    pending_started_at: datetime | None = None
    pending_frames: int = 0
    invalid_streak: int = 0
    recovery_frames: int = 0
    recovery_started_at: datetime | None = None
    recovery_target: OccupancyState | None = None
    last_confirmed_at: datetime | None = None
    last_confirmed_state: OccupancyState | None = None
    evidence_history: deque[EvidenceSample] = field(default_factory=deque)

    def snapshot_confidence(self) -> float:
        return self.confidence


class OccupancyStateMachine:
    """Stabilize occupancy for a single parking space over time.

    Parameters
    ----------
    space_id:
        Stable parking-space identifier.
    geometry:
        Enter/exit score thresholds (hysteresis).
    state:
        Confirmation mode, frame/time thresholds, unknown streak.
    clock:
        Injected UTC clock (tests freeze time via a fake clock).
    history_maxlen:
        Bound on retained evidence samples (acceptance: history stays bounded).
    """

    def __init__(
        self,
        space_id: str,
        geometry: GeometrySettings,
        state: StateSettings,
        clock: Clock | None = None,
        *,
        history_maxlen: int = DEFAULT_EVIDENCE_HISTORY_MAXLEN,
    ) -> None:
        if history_maxlen < 1:
            raise ValueError("history_maxlen must be >= 1.")
        self._geometry = geometry
        self._state = state
        self._clock: Clock = clock if clock is not None else SystemClock()
        self._history_maxlen = history_maxlen
        self._runtime = SpaceRuntimeState(
            space_id=space_id,
            evidence_history=deque(maxlen=history_maxlen),
        )

    @property
    def space_id(self) -> str:
        return self._runtime.space_id

    @property
    def state(self) -> OccupancyState:
        return self._runtime.state

    @property
    def confidence(self) -> float:
        return self._runtime.confidence

    @property
    def last_score(self) -> float:
        return self._runtime.last_score

    @property
    def track_id(self) -> str | None:
        return self._runtime.track_id

    @property
    def evidence_history(self) -> tuple[EvidenceSample, ...]:
        return tuple(self._runtime.evidence_history)

    @property
    def history_maxlen(self) -> int:
        return self._history_maxlen

    @property
    def runtime(self) -> SpaceRuntimeState:
        return self._runtime

    def update(
        self,
        score: float,
        *,
        frame_valid: bool = True,
        track_id: str | None = None,
        observed_at: datetime | None = None,
    ) -> OccupancyState:
        """Ingest one observation and return the resulting occupancy state."""
        now = observed_at if observed_at is not None else self._clock.now()
        if now.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware (UTC).")

        sample = EvidenceSample(
            score=float(score),
            valid=frame_valid,
            observed_at=now,
            track_id=track_id,
        )
        self._runtime.evidence_history.append(sample)
        self._runtime.last_score = sample.score
        if track_id is not None:
            self._runtime.track_id = track_id

        if not frame_valid:
            return self._handle_invalid(now)

        self._runtime.invalid_streak = 0
        return self._handle_valid(sample.score, now)

    def _handle_invalid(self, now: datetime) -> OccupancyState:
        self._runtime.invalid_streak += 1
        self._clear_pending()
        self._clear_recovery()
        self._runtime.confidence = min(self._runtime.confidence, 0.25)

        if (
            self._runtime.state != OccupancyState.UNKNOWN
            and self._runtime.invalid_streak >= self._state.unknown_after_invalid_frames
        ):
            self._set_state(OccupancyState.UNKNOWN, now, confidence=0.0)
        return self._runtime.state

    def _handle_valid(self, score: float, now: datetime) -> OccupancyState:
        current = self._runtime.state
        if current == OccupancyState.UNKNOWN:
            return self._update_unknown(score, now)
        if current == OccupancyState.AVAILABLE:
            return self._update_available(score, now)
        if current == OccupancyState.PENDING_OCCUPIED:
            return self._update_pending_occupied(score, now)
        if current == OccupancyState.OCCUPIED:
            return self._update_occupied(score, now)
        if current == OccupancyState.PENDING_AVAILABLE:
            return self._update_pending_available(score, now)
        # Defensive fallback — should be unreachable with OccupancyState enum.
        return self._update_unknown(score, now)

    def _update_unknown(self, score: float, now: datetime) -> OccupancyState:
        enter = self._geometry.occupied_enter_threshold
        target = OccupancyState.OCCUPIED if score >= enter else OccupancyState.AVAILABLE

        if self._runtime.recovery_target != target:
            self._runtime.recovery_target = target
            self._runtime.recovery_frames = 0
            self._runtime.recovery_started_at = now

        self._runtime.recovery_frames += 1
        self._runtime.confidence = self._confidence_from_score(score, pending=True)

        if self._confirmation_met(
            frames=self._runtime.recovery_frames,
            started_at=self._runtime.recovery_started_at or now,
            now=now,
            entering=True,
        ):
            self._clear_recovery()
            self._set_state(target, now, confidence=self._confidence_from_score(score))
        return self._runtime.state

    def _update_available(self, score: float, now: datetime) -> OccupancyState:
        if score >= self._geometry.occupied_enter_threshold:
            self._begin_pending(OccupancyState.PENDING_OCCUPIED, now)
            return self._update_pending_occupied(score, now, count_frame=False)
        self._runtime.confidence = self._confidence_from_score(score)
        return self._runtime.state

    def _update_pending_occupied(
        self,
        score: float,
        now: datetime,
        *,
        count_frame: bool = True,
    ) -> OccupancyState:
        if score < self._geometry.occupied_enter_threshold:
            # Evidence fell — cancel pending enter.
            self._clear_pending()
            self._set_state(
                OccupancyState.AVAILABLE,
                now,
                confidence=self._confidence_from_score(score),
                confirmed=False,
            )
            return self._runtime.state

        if count_frame:
            self._runtime.pending_frames += 1
        self._runtime.confidence = self._confidence_from_score(score, pending=True)
        if self._confirmation_met(
            frames=self._runtime.pending_frames,
            started_at=self._runtime.pending_started_at or now,
            now=now,
            entering=True,
        ):
            self._clear_pending()
            self._set_state(
                OccupancyState.OCCUPIED,
                now,
                confidence=self._confidence_from_score(score),
            )
        return self._runtime.state

    def _update_occupied(self, score: float, now: datetime) -> OccupancyState:
        if score <= self._geometry.occupied_exit_threshold:
            self._begin_pending(OccupancyState.PENDING_AVAILABLE, now)
            return self._update_pending_available(score, now, count_frame=False)
        self._runtime.confidence = self._confidence_from_score(score)
        return self._runtime.state

    def _update_pending_available(
        self,
        score: float,
        now: datetime,
        *,
        count_frame: bool = True,
    ) -> OccupancyState:
        if score > self._geometry.occupied_exit_threshold:
            # Evidence rose — cancel pending exit.
            self._clear_pending()
            self._set_state(
                OccupancyState.OCCUPIED,
                now,
                confidence=self._confidence_from_score(score),
                confirmed=False,
            )
            return self._runtime.state

        if count_frame:
            self._runtime.pending_frames += 1
        self._runtime.confidence = self._confidence_from_score(score, pending=True)
        if self._confirmation_met(
            frames=self._runtime.pending_frames,
            started_at=self._runtime.pending_started_at or now,
            now=now,
            entering=False,
        ):
            self._clear_pending()
            self._set_state(
                OccupancyState.AVAILABLE,
                now,
                confidence=self._confidence_from_score(score),
            )
        return self._runtime.state

    def _begin_pending(self, pending_state: OccupancyState, now: datetime) -> None:
        self._runtime.state = pending_state
        self._runtime.pending_started_at = now
        self._runtime.pending_frames = 1

    def _clear_pending(self) -> None:
        self._runtime.pending_started_at = None
        self._runtime.pending_frames = 0

    def _clear_recovery(self) -> None:
        self._runtime.recovery_frames = 0
        self._runtime.recovery_started_at = None
        self._runtime.recovery_target = None

    def _set_state(
        self,
        new_state: OccupancyState,
        now: datetime,
        *,
        confidence: float,
        confirmed: bool = True,
    ) -> None:
        self._runtime.state = new_state
        self._runtime.confidence = confidence
        if confirmed and new_state in {
            OccupancyState.AVAILABLE,
            OccupancyState.OCCUPIED,
            OccupancyState.UNKNOWN,
        }:
            self._runtime.last_confirmed_at = now
            self._runtime.last_confirmed_state = new_state

    def _confirmation_met(
        self,
        *,
        frames: int,
        started_at: datetime,
        now: datetime,
        entering: bool,
    ) -> bool:
        if self._state.mode == "frames":
            needed = (
                self._state.enter_confirm_frames if entering else self._state.exit_confirm_frames
            )
            return frames >= needed

        needed_seconds = (
            self._state.enter_confirm_seconds if entering else self._state.exit_confirm_seconds
        )
        elapsed = (now - started_at).total_seconds()
        return elapsed >= needed_seconds

    @staticmethod
    def _confidence_from_score(score: float, *, pending: bool = False) -> float:
        clamped = max(0.0, min(1.0, float(score)))
        if pending:
            return max(0.15, min(0.85, clamped * 0.9))
        return clamped

"""Runtime invariant engine.

Invariants are assertions checked at each cycle boundary. A violation
raises InvariantViolation, halting the simulation before the bad state
is committed to memory. This is the UAF equivalent of a contract checker.

Adding a new invariant: subclass Invariant, implement check(), register
it in the InvariantSet. No other changes needed.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from uaf.kernel.state import CycleState, VerificationResult


class InvariantViolation(Exception):
    """Raised when a runtime invariant is breached."""


class Invariant(ABC):
    """A single runtime assertion."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def check(self, state: CycleState) -> None:
        """Raise InvariantViolation if the invariant is breached."""


# ------------------------------------------------------------------ #
# Built-in invariants                                                 #
# ------------------------------------------------------------------ #


class ScoreInRange(Invariant):
    """composite_score must stay within [0.0, 5.0]."""

    name = "score_in_range"

    def check(self, state: CycleState) -> None:
        s = state.composite_score
        if not (0.0 <= s <= 5.0):
            raise InvariantViolation(
                f"[{self.name}] composite_score={s:.4f} out of [0.0, 5.0]"
            )


class CandidateNotEmpty(Invariant):
    """candidate must be a non-empty string."""

    name = "candidate_not_empty"

    def check(self, state: CycleState) -> None:
        if not state.candidate or not state.candidate.strip():
            raise InvariantViolation(
                f"[{self.name}] candidate is empty at cycle {state.cycle}"
            )


class ScoreHistoryMonotoneOrPlateau(Invariant):
    """Score history must not regress more than 0.5 in a single cycle.

    Large unexplained drops (> 0.5) are a sign of evaluator instability
    or state corruption, not genuine degradation.
    """

    name = "score_no_catastrophic_regression"
    MAX_REGRESSION = 0.5

    def check(self, state: CycleState) -> None:
        delta = state.plateau_delta
        if delta is not None and delta < -self.MAX_REGRESSION:
            raise InvariantViolation(
                f"[{self.name}] Score regressed by {-delta:.4f} at cycle {state.cycle} "
                f"(max allowed: {self.MAX_REGRESSION})"
            )


class GoodhartWarningsBounded(Invariant):
    """Goodhart warnings must not exceed max_warnings."""

    name = "goodhart_warnings_bounded"

    def __init__(self, max_warnings: int = 10) -> None:
        self._max = max_warnings

    def check(self, state: CycleState) -> None:
        if state.goodhart_warnings > self._max:
            raise InvariantViolation(
                f"[{self.name}] goodhart_warnings={state.goodhart_warnings} "
                f"exceeds max={self._max} — possible reward hacking loop"
            )


class AuditRecordEmitted(Invariant):
    """An audit record must be present in metadata when force_save is True.

    This invariant only fires on save cycles, preventing silent loss of
    the audit trail.
    """

    name = "audit_record_emitted_on_save"

    def check(self, state: CycleState) -> None:
        if state.force_save and "audit_record" not in state.metadata:
            raise InvariantViolation(
                f"[{self.name}] force_save=True at cycle {state.cycle} "
                "but no 'audit_record' key in state.metadata"
            )


# ------------------------------------------------------------------ #
# InvariantSet — the runtime enforcer                                 #
# ------------------------------------------------------------------ #


@dataclass
class InvariantSet:
    """Collection of invariants checked together at each cycle boundary."""

    invariants: list[Invariant]

    def check_all(self, state: CycleState) -> list[InvariantViolation]:
        """Check all invariants and return any violations (non-raising mode).

        Use enforce() to raise on first violation.
        """
        violations = []
        for inv in self.invariants:
            try:
                inv.check(state)
            except InvariantViolation as e:
                violations.append(e)
        return violations

    def enforce(self, state: CycleState) -> None:
        """Check all invariants. Raise on the first violation found."""
        for inv in self.invariants:
            inv.check(state)

    @classmethod
    def default(cls) -> "InvariantSet":
        """Return the default invariant set for creative evolution experiments."""
        return cls(invariants=[
            ScoreInRange(),
            CandidateNotEmpty(),
            ScoreHistoryMonotoneOrPlateau(),
            GoodhartWarningsBounded(max_warnings=10),
        ])

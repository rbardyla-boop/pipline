"""Frozen state types shared across all UAF components.

These are pure data containers — no behaviour, no imports from within uaf/.
Keeping them in a dedicated module prevents circular imports between
uaf/interfaces/ and uaf/kernel/.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SimulationContext:
    """Immutable setup context for a single simulation run."""

    domain: str
    seeds: tuple[str, ...]
    run_id: str
    config: dict[str, Any] = field(default_factory=dict)

    def with_config(self, **overrides: Any) -> "SimulationContext":
        return SimulationContext(
            domain=self.domain,
            seeds=self.seeds,
            run_id=self.run_id,
            config={**self.config, **overrides},
        )


@dataclass(frozen=True)
class VerificationResult:
    """Result produced by a VerificationEngine for a single candidate."""

    composite_score: float
    criteria_scores: dict[str, float]
    ritual_cost_score: float
    anti_optimization_score: float
    improvement_context: str
    goodhart_warning: bool
    verdict: str                  # "HIT" | "SLOP" | "COUNTER_SIGNAL"
    extended_verdict: str
    sandbox_results: dict[str, Any] | None = None


@dataclass(frozen=True)
class CycleState:
    """Snapshot of simulator state at the end of one execution cycle.

    This is a read-only projection consumed by Planner and the dynamics
    layer. The legacy PipelineState remains the authoritative mutable
    store inside orchestrator.py through Phases 1–5; CycleState wraps
    a consistent read view of it.
    """

    cycle: int
    candidate: str
    composite_score: float
    score_history: tuple[float, ...]
    goodhart_warnings: int
    force_save: bool
    verification: VerificationResult | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def plateau_delta(self) -> float | None:
        """Score improvement since the previous cycle, or None on cycle 0."""
        if len(self.score_history) < 2:
            return None
        return self.score_history[-1] - self.score_history[-2]

    @property
    def is_first_cycle(self) -> bool:
        return self.cycle == 0

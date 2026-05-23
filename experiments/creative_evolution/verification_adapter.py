"""PhoenixVerification — wraps ConceptRater + CulturalSandbox as a VerificationEngine.

ConceptRater handles the Phoenix rubric (5-criterion scoring, Goodhart detection).
CulturalSandbox handles the behavioural simulation (viral velocity, memetic drift).

The adapter tracks the previous top-candidate embedding across calls to detect
Goodhart convergence (cosine similarity > CONVERGENCE_THRESHOLD).

NOTE: Importing this module triggers concept_rater.py's sys.path.insert to
resolve the external clovelearn_phoenix dependency. This is load-bearing and
must not be interfered with. The import path must resolve relative to
concept_rater.py's own __file__ location, which it will as long as the
pipline/ directory is the working directory or on sys.path.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from uaf.interfaces.verification import VerificationEngine
from uaf.kernel.state import SimulationContext, VerificationResult

if TYPE_CHECKING:
    from concept_rater import ConceptRater


class PhoenixVerification(VerificationEngine):
    """VerificationEngine backed by ConceptRater + CulturalSandbox.

    Args:
        rater:  A ConceptRater instance (wraps Claude, applies Phoenix rubric).
        engine: The shared NoveltySearchEngine (for embedding Goodhart detection).
        run_sandbox: Whether to run the CulturalSandbox simulation each cycle.
                     Default True. Set False to speed up tests/dry-runs.
    """

    def __init__(
        self,
        rater: "ConceptRater",
        engine,  # NoveltySearchEngine — typed loosely to avoid circular import
        run_sandbox: bool = True,
    ) -> None:
        self._rater = rater
        self._engine = engine
        self._run_sandbox = run_sandbox
        self._prev_embedding: np.ndarray | None = None

    # ------------------------------------------------------------------ #
    # VerificationEngine                                                  #
    # ------------------------------------------------------------------ #

    def score(self, candidate: str, ctx: SimulationContext) -> VerificationResult:
        domain = ctx.domain

        # Phoenix rubric
        rating = self._rater.rate(candidate, domain)
        composite: float = rating["composite"]
        criteria_scores: dict = rating["scores"]
        improvement_context: str = rating["improvement_context"]
        ritual_cost: float = rating["ritual_cost_score"]
        anti_opt: float = rating["anti_optimization_score"]

        # Goodhart convergence detection (embedding-level)
        current_emb: np.ndarray = self._engine.embed(candidate)
        goodhart_warning = False
        if self._prev_embedding is not None:
            goodhart_warning = self._rater.detect_convergence(
                self._prev_embedding, current_emb
            )
        self._prev_embedding = current_emb

        # Cultural sandbox (optional)
        sandbox_results: dict | None = None
        extended_verdict = "SLOP"
        if self._run_sandbox:
            from sandbox import CulturalSandbox
            sandbox = CulturalSandbox(domain=domain, weeks=5)
            sandbox_results = sandbox.run(candidate, verbose=False)
            extended_verdict = sandbox_results["metrics"]["verdict"]

        return VerificationResult(
            composite_score=composite,
            criteria_scores=criteria_scores,
            ritual_cost_score=ritual_cost,
            anti_optimization_score=anti_opt,
            improvement_context=improvement_context,
            goodhart_warning=goodhart_warning,
            verdict=extended_verdict,
            extended_verdict=extended_verdict,
            sandbox_results=sandbox_results,
        )

    def verdict(self, result: VerificationResult) -> str:
        return result.extended_verdict

    # ------------------------------------------------------------------ #
    # State reset (for new runs)                                          #
    # ------------------------------------------------------------------ #

    def reset(self) -> None:
        """Clear previous embedding state. Call at the start of each run."""
        self._prev_embedding = None

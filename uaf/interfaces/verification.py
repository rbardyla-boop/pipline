"""VerificationEngine — reality-grounded evaluation interface.

Verification is a transactional commit gate: no candidate advances to
memory unless it passes. The verification engine is the only place where
multi-criterion scoring, behavioural simulation, and signal detection
combine into a single VerificationResult.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from uaf.kernel.state import SimulationContext, VerificationResult


class VerificationEngine(ABC):
    """Transactional evaluation gate.

    Implementations wrap whatever domain-specific scoring machinery is
    relevant (e.g. Phoenix rubric + CulturalSandbox for the creative
    evolution experiment).
    """

    @abstractmethod
    def score(self, candidate: str, ctx: SimulationContext) -> VerificationResult:
        """Evaluate *candidate* and return a complete VerificationResult.

        This is the primary entry point. Implementations should:
          1. Run all scoring criteria.
          2. Run behavioural / cultural simulation if applicable.
          3. Detect anti-patterns (Goodhart convergence, reward hacking).
          4. Populate all fields of VerificationResult.

        Args:
            candidate: The concept string to evaluate.
            ctx:       The simulation context (domain, config, etc.).

        Returns:
            A fully populated VerificationResult. Must never raise.
        """

    @abstractmethod
    def verdict(self, result: VerificationResult) -> str:
        """Derive a single verdict string from *result*.

        Returns one of: "HIT", "SLOP", "COUNTER_SIGNAL".

        Implementations may incorporate sandbox results, signal scores,
        and composite thresholds to make this determination.
        """

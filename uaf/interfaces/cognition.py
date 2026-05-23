"""CognitionEngine — the pluggable reasoning substrate interface.

Any architecture (LLM, symbolic, hybrid, sparse, etc.) that can produce
candidate strings, embed them, and estimate their coherence satisfies
this contract and can be driven by the UAF simulation kernel.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence


class CognitionEngine(ABC):
    """Pluggable reasoning substrate.

    Implementations must be stateless between calls; any persistent state
    must flow through the MemorySystem rather than being held here.
    Reasoning traces must be surfaced via the optional trace_* methods so
    the dynamics layer can observe cognitive behaviour across cycles.
    """

    # ------------------------------------------------------------------ #
    # Required                                                            #
    # ------------------------------------------------------------------ #

    @abstractmethod
    def propose(self, parent: str, context: str) -> str:
        """Generate a mutated candidate from *parent* given *context*.

        Args:
            parent:  The current best candidate concept string.
            context: Cultural / zeitgeist context injected by the runtime.

        Returns:
            A new candidate string. Must differ from *parent*.
        """

    @abstractmethod
    def embed(self, text: str) -> Sequence[float]:
        """Return a dense embedding vector for *text*."""

    @abstractmethod
    def coherence(self, candidate: str) -> float:
        """Estimate how internally coherent *candidate* is.

        Returns:
            A float in [0.0, 1.0] where 1.0 is maximally coherent.
        """

    @property
    @abstractmethod
    def architecture_id(self) -> str:
        """Stable identifier for this architecture (e.g. 'claude_novelty_v1').

        Used as a key in the experiment ledger. Must not change between
        runs of the same architecture configuration.
        """

    # ------------------------------------------------------------------ #
    # Optional hooks for the dynamics layer                               #
    # ------------------------------------------------------------------ #

    def reasoning_trace(self) -> list[str]:
        """Return the reasoning steps from the most recent propose() call.

        Default: empty list (trace not available for this architecture).
        """
        return []

    def uncertainty_map(self) -> dict[str, float]:
        """Return per-token or per-concept uncertainty estimates.

        Default: empty dict.
        """
        return {}

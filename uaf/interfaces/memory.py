"""MemorySystem — multi-layer cognitive state persistence interface.

Memory in the UAF is lossy, evolving, and entropy-bounded — it is not a
plain key-value store. Implementations must model decay, compression, and
cross-run persistence (the terminal archive) alongside within-session
trajectory tracking.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence


class MemorySystem(ABC):
    """Multi-layer cognitive state persistence."""

    # ------------------------------------------------------------------ #
    # Lifecycle                                                           #
    # ------------------------------------------------------------------ #

    @abstractmethod
    def seed(self, items: list[str]) -> None:
        """Populate the archive with the initial seed concepts.

        Called once at simulation start before the first cycle.
        """

    # ------------------------------------------------------------------ #
    # Within-run write path                                               #
    # ------------------------------------------------------------------ #

    @abstractmethod
    def add(
        self,
        item: str,
        embedding: Sequence[float],
        novelty: float,
        generation: int,
    ) -> None:
        """Record a newly evolved candidate into the working archive.

        Args:
            item:       The candidate concept string.
            embedding:  Dense embedding vector from the cognition engine.
            novelty:    Computed novelty score [0.0, 1.0].
            generation: Which evolution generation produced this item.
        """

    # ------------------------------------------------------------------ #
    # Read path                                                           #
    # ------------------------------------------------------------------ #

    @abstractmethod
    def novelty_of(self, embedding: Sequence[float]) -> float:
        """Return the novelty score of *embedding* relative to the archive.

        Typically the minimum cosine distance to all archived embeddings.
        Returns 1.0 (maximally novel) when the archive is empty.
        """

    @abstractmethod
    def retired_ids(self) -> set[str]:
        """Return the set of concept strings already in the terminal archive.

        Used by the planner/invariant engine to prevent terminal concepts
        from re-surfacing in new runs.
        """

    # ------------------------------------------------------------------ #
    # Cross-run persistence                                               #
    # ------------------------------------------------------------------ #

    @abstractmethod
    def retire(self, item: str, score: float, combined: float, run_id: str) -> None:
        """Permanently archive *item* in the terminal (cross-run) store.

        Called when a concept passes both Phoenix and combined thresholds.
        """

    # ------------------------------------------------------------------ #
    # Dynamics layer hook                                                 #
    # ------------------------------------------------------------------ #

    @abstractmethod
    def session_snapshot(self) -> dict:
        """Return a serialisable snapshot of current session state.

        Consumed by the dynamics recorder at the end of each cycle.
        Must include at minimum:
          - 'archive_size': int
          - 'session_embeddings': list[list[float]]  (recent cycle embeddings)
          - 'refractory_clusters': list  (locked phrase clusters if any)
        """

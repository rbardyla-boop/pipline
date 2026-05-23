"""ArchiveMemory — wraps NoveltySearchEngine archive + V5Simulator session state.

This adapter presents a unified MemorySystem interface over two distinct
stores that currently live in separate places:
  1. Working archive: NoveltySearchEngine.archive (in-memory, within-run)
  2. Terminal archive: logs/terminal_archive.json (cross-run persistent)
  3. Session trajectory: V5Simulator state (within-run, for dynamics layer)

The engine instance must be the same one passed to ClaudeNoveltyCognition.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

import numpy as np

from uaf.interfaces.memory import MemorySystem

if TYPE_CHECKING:
    from engine import NoveltySearchEngine


class ArchiveMemory(MemorySystem):
    """MemorySystem backed by NoveltySearchEngine + V5 session tracking.

    Args:
        engine: The shared NoveltySearchEngine instance.
    """

    def __init__(self, engine: "NoveltySearchEngine") -> None:
        self._engine = engine
        # V5 session state (mirrors what PipelineState holds)
        self._session_embeddings: list[dict] = []
        self._refractory_clusters: list[dict] = []
        self._trajectory_warnings: int = 0
        self._current_cycle: int = 0

    # ------------------------------------------------------------------ #
    # MemorySystem                                                        #
    # ------------------------------------------------------------------ #

    def seed(self, items: list[str]) -> None:
        self._engine.seed_archive(items)

    def add(
        self,
        item: str,
        embedding: Sequence[float],
        novelty: float,
        generation: int,
    ) -> None:
        emb = np.array(embedding)
        # Respect the novelty threshold gate the engine enforces during evolve()
        if novelty > self._engine.threshold:
            self._engine.archive.append({
                "concept": item,
                "embedding": emb,
                "generation": generation,
                "novelty": novelty,
            })
            self._engine.prune_archive()

    def novelty_of(self, embedding: Sequence[float]) -> float:
        return self._engine.novelty_score(np.array(embedding))

    def retired_ids(self) -> set[str]:
        return self._engine.load_terminal_archive()

    def retire(self, item: str, score: float, combined: float, run_id: str) -> None:
        self._engine.write_terminal_archive(item, score, combined, run_id)

    def session_snapshot(self) -> dict:
        return {
            "archive_size": len(self._engine.archive),
            "session_embeddings": [
                {k: v if k != "emb_list" else list(v) for k, v in e.items()}
                for e in self._session_embeddings
            ],
            "refractory_clusters": list(self._refractory_clusters),
            "trajectory_warnings": self._trajectory_warnings,
            "current_cycle": self._current_cycle,
        }

    # ------------------------------------------------------------------ #
    # V5 session tracking (called by the simulation kernel / planner)    #
    # ------------------------------------------------------------------ #

    def update_v5_session(self, concept: str, embedding: Sequence[float]) -> None:
        """Record the top candidate for the current cycle (V5 trajectory tracking)."""
        from simulator import V5Simulator

        new_emb = np.array(embedding)
        new_session, new_refractory, new_warnings = V5Simulator.update_session(
            self._session_embeddings,
            self._refractory_clusters,
            self._trajectory_warnings,
            self._current_cycle,
            new_emb,
            concept,
        )
        self._session_embeddings = new_session
        self._refractory_clusters = new_refractory
        self._trajectory_warnings = new_warnings
        self._current_cycle += 1

    def v5_context_block(self) -> str:
        """Return the V5 simulator context block to prepend to zeitgeist context."""
        from simulator import V5Simulator

        return V5Simulator.build_context(
            self._session_embeddings,
            self._refractory_clusters,
            self._current_cycle,
        )

    def load_from_pipeline_state(self, state: dict) -> None:
        """Sync V5 state from an existing PipelineState dict.

        Used during Phase 6 cutover so the memory adapter starts from
        whatever state the legacy LangGraph pipeline has accumulated.
        """
        self._session_embeddings = list(state.get("simulator_session_embeddings", []))
        self._refractory_clusters = list(state.get("simulator_refractory_clusters", []))
        self._trajectory_warnings = int(state.get("simulator_trajectory_warnings", 0))
        self._current_cycle = int(state.get("refinement_loop_count", 0))

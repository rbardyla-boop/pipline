"""ClaudeNoveltyCognition — wraps NoveltySearchEngine as a CognitionEngine.

This adapter is the bridge between the existing engine.py implementation
and the UAF CognitionEngine interface. It delegates all operations to the
shared NoveltySearchEngine instance (which owns the SentenceTransformer
model and the Anthropic client).

Both this adapter and ArchiveMemory (experiments/creative_evolution/memory_adapter.py)
must receive the *same* engine instance so they share the archive state.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

import numpy as np

from uaf.interfaces.cognition import CognitionEngine

if TYPE_CHECKING:
    from engine import NoveltySearchEngine


class ClaudeNoveltyCognition(CognitionEngine):
    """CognitionEngine implementation backed by Claude Sonnet + SentenceTransformer.

    Args:
        engine: A fully initialised NoveltySearchEngine instance. Must not
                be None. Pass the same instance to ArchiveMemory so they
                share the in-memory archive.
    """

    def __init__(self, engine: "NoveltySearchEngine") -> None:
        self._engine = engine
        self._last_trace: list[str] = []

    # ------------------------------------------------------------------ #
    # CognitionEngine                                                     #
    # ------------------------------------------------------------------ #

    def propose(self, parent: str, context: str) -> str:
        """Delegate to NoveltySearchEngine.mutate()."""
        result = self._engine.mutate(parent, context)
        self._last_trace = [f"mutate({parent[:40]}...) via Claude Sonnet"]
        return result

    def embed(self, text: str) -> Sequence[float]:
        """Delegate to NoveltySearchEngine.embed() (SentenceTransformer)."""
        arr: np.ndarray = self._engine.embed(text)
        return arr.tolist()

    def coherence(self, candidate: str) -> float:
        """Delegate to NoveltySearchEngine.coherence_score()."""
        return self._engine.coherence_score(candidate)

    @property
    def architecture_id(self) -> str:
        return "claude_novelty_v1"

    # ------------------------------------------------------------------ #
    # Dynamics hooks                                                      #
    # ------------------------------------------------------------------ #

    def reasoning_trace(self) -> list[str]:
        return list(self._last_trace)

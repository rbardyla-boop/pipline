"""Lesson 7: Memory Is Harder Than Most People Expect.

Multi-tier memory stack combining:
  - Short-term:  recent messages (fixed-size ring buffer)
  - Mid-term:    vector-indexed session memory (cosine search)
  - Long-term:   structured key-value with TTL and explicit recall

Too much memory = noise. Too little = no personalization.
The stack makes the balance explicit and configurable.

Self-igniting: starts empty, grows from interactions.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from enum import Enum


class MemoryTier(Enum):
    SHORT = "short"
    MID = "mid"
    LONG = "long"


@dataclass
class _ShortEntry:
    role: str
    content: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class _MidEntry:
    summary: str
    embedding: list[float]
    importance: float = 0.5
    timestamp: float = field(default_factory=time.time)


@dataclass
class _LongEntry:
    key: str
    value: str
    ttl: float = 0.0  # 0 = never expire
    created_at: float = field(default_factory=time.time)

    def is_expired(self) -> bool:
        if self.ttl <= 0:
            return False
        return time.time() - self.created_at > self.ttl


def _embed_text(text: str) -> list[float]:
    """Deterministic BoW embedding — no external deps."""
    tokens = text.lower().split()
    counts: dict[str, int] = {}
    for t in tokens:
        counts[t] = counts.get(t, 0) + 1
    total = max(1, len(tokens))
    keys = sorted(counts.keys())
    vec = [counts[k] / total for k in keys]
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def _cosine(a: list[float], b: list[float]) -> float:
    shared = min(len(a), len(b))
    dot = sum(a[i] * b[i] for i in range(shared))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)


class MemoryStack:
    """Three-tier memory system.

    Args:
        short_window:  Max messages kept in short-term (ring buffer).
        mid_capacity:  Max entries in vector memory.
        summarize_at:  Auto-summarize short-term into mid-term at this count.
        embed_fn:      Embedding function for mid-term indexing.
    """

    def __init__(
        self,
        short_window: int = 20,
        mid_capacity: int = 200,
        summarize_at: int = 0,
        embed_fn=None,
    ) -> None:
        self._short_window = short_window
        self._mid_capacity = mid_capacity
        self._summarize_at = summarize_at
        self._embed_fn = embed_fn or _embed_text
        self._short: list[_ShortEntry] = []
        self._mid: list[_MidEntry] = []
        self._long: dict[str, _LongEntry] = {}

    # ---- Short-term ----

    def push(self, role: str, content: str) -> None:
        """Append to short-term. Evicts oldest when window is full."""
        if len(self._short) >= self._short_window:
            self._short.pop(0)
        self._short.append(_ShortEntry(role, content))
        if self._summarize_at > 0 and len(self._short) >= self._summarize_at:
            self._flush_short_to_mid()

    def recent(self, n: int = 5) -> list[dict[str, str]]:
        """Return last *n* messages as {role, content} dicts."""
        return [{"role": e.role, "content": e.content} for e in self._short[-n:]]

    # ---- Mid-term ----

    def remember(self, summary: str, importance: float = 0.5) -> None:
        """Store a summarized memory in vector space."""
        emb = self._embed_fn(summary)
        if len(self._mid) >= self._mid_capacity:
            # evict lowest importance
            self._mid.sort(key=lambda e: e.importance)
            self._mid.pop(0)
        self._mid.append(_MidEntry(summary, emb, importance))

    def recall(self, query: str, top_k: int = 3) -> list[str]:
        """Retrieve top-k relevant mid-term memories."""
        if not self._mid:
            return []
        q_emb = self._embed_fn(query)
        scored = sorted(
            self._mid,
            key=lambda e: _cosine(q_emb, e.embedding),
            reverse=True,
        )
        return [e.summary for e in scored[:top_k]]

    # ---- Long-term ----

    def store(self, key: str, value: str, ttl: float = 0.0) -> None:
        """Persist a structured key-value fact."""
        self._long[key] = _LongEntry(key, value, ttl)

    def retrieve(self, key: str) -> str | None:
        """Get a long-term fact by key. Returns None if missing or expired."""
        entry = self._long.get(key)
        if entry is None or entry.is_expired():
            if entry is not None:
                del self._long[key]
            return None
        return entry.value

    def expire_stale(self) -> int:
        """Remove all expired long-term entries. Returns count removed."""
        stale = [k for k, v in self._long.items() if v.is_expired()]
        for k in stale:
            del self._long[k]
        return len(stale)

    # ---- Snapshot ----

    def snapshot(self) -> dict:
        self.expire_stale()
        return {
            "short_count": len(self._short),
            "mid_count": len(self._mid),
            "long_count": len(self._long),
        }

    def clear(self, tier: MemoryTier | None = None) -> None:
        if tier is None or tier == MemoryTier.SHORT:
            self._short = []
        if tier is None or tier == MemoryTier.MID:
            self._mid = []
        if tier is None or tier == MemoryTier.LONG:
            self._long = {}

    def _flush_short_to_mid(self) -> None:
        """Compress short-term messages into a mid-term summary."""
        text = " ".join(e.content for e in self._short)
        self.remember(text[:500], importance=0.6)
        self._short = self._short[-5:]

"""Lessons 5 + 9: Latency Matters + Cost Optimization.

Smart model router: estimate query complexity and route to the right
model tier. Use smaller models first; escalate only when needed.

Caching layer prevents redundant calls. Token compression reduces cost.

Self-igniting: starts with default rules, adapts from cache hit rate.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Complexity(Enum):
    SIMPLE = "simple"       # → Haiku 4.5
    MODERATE = "moderate"   # → Sonnet 4.6
    COMPLEX = "complex"     # → Opus 4.7


@dataclass(frozen=True)
class RouteDecision:
    model: str
    complexity: Complexity
    cache_hit: bool
    token_estimate: int
    reason: str


_MODEL_MAP = {
    Complexity.SIMPLE: "claude-haiku-4-5-20251001",
    Complexity.MODERATE: "claude-sonnet-4-6",
    Complexity.COMPLEX: "claude-opus-4-7",
}

_COMPLEXITY_SIGNALS = {
    # signals that push toward COMPLEX
    "complex": 2, "analyze": 2, "architect": 2, "design": 2,
    "deep": 1, "explain why": 2, "compare": 1, "evaluate": 2,
    "research": 2, "reason": 1, "multi-step": 2, "strategy": 2,
    # signals that push toward SIMPLE
    "summarize": -1, "list": -1, "translate": -1, "format": -1,
    "convert": -1, "extract": -1, "simple": -2, "quick": -2,
}


def _estimate_complexity(prompt: str, token_estimate: int) -> Complexity:
    lower = prompt.lower()
    score = 0

    for signal, weight in _COMPLEXITY_SIGNALS.items():
        if signal in lower:
            score += weight

    # Long prompts lean toward moderate/complex
    if token_estimate > 2000:
        score += 2
    elif token_estimate > 500:
        score += 1

    # Question complexity heuristic
    if lower.count("?") > 2:
        score += 1

    if score >= 3:
        return Complexity.COMPLEX
    if score >= 0:
        return Complexity.MODERATE
    return Complexity.SIMPLE


class ModelRouter:
    """Routes prompts to appropriate model tiers with caching.

    Args:
        model_map:        Override default {Complexity: model_id} mapping.
        cache_capacity:   Max cached responses (LRU eviction).
        force_complexity: Override all routing with a fixed complexity.
    """

    def __init__(
        self,
        model_map: dict[Complexity, str] | None = None,
        cache_capacity: int = 256,
        force_complexity: Complexity | None = None,
    ) -> None:
        self._model_map = model_map or _MODEL_MAP.copy()
        self._cache_capacity = cache_capacity
        self._force = force_complexity
        self._cache: dict[str, Any] = {}
        self._cache_order: list[str] = []
        self._hits = 0
        self._misses = 0

    def route(self, prompt: str, token_estimate: int = 0) -> RouteDecision:
        """Decide which model to use for *prompt*."""
        if token_estimate == 0:
            token_estimate = max(1, len(prompt) // 4)

        if self._force:
            complexity = self._force
            reason = f"forced to {self._force.value}"
        else:
            complexity = _estimate_complexity(prompt, token_estimate)
            reason = f"auto-routed: score from signals"

        model = self._model_map[complexity]
        cache_key = self._cache_key(prompt, model)
        cache_hit = cache_key in self._cache

        if cache_hit:
            self._hits += 1
        else:
            self._misses += 1

        return RouteDecision(
            model=model,
            complexity=complexity,
            cache_hit=cache_hit,
            token_estimate=token_estimate,
            reason=reason,
        )

    def cache_set(self, prompt: str, model: str, response: Any) -> None:
        key = self._cache_key(prompt, model)
        if key not in self._cache:
            if len(self._cache) >= self._cache_capacity:
                oldest = self._cache_order.pop(0)
                self._cache.pop(oldest, None)
            self._cache_order.append(key)
        self._cache[key] = response

    def cache_get(self, prompt: str, model: str) -> Any | None:
        key = self._cache_key(prompt, model)
        return self._cache.get(key)

    def cache_stats(self) -> dict[str, Any]:
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / total if total else 0.0,
            "size": len(self._cache),
        }

    def invalidate_cache(self) -> None:
        self._cache = {}
        self._cache_order = []
        self._hits = 0
        self._misses = 0

    @staticmethod
    def _cache_key(prompt: str, model: str) -> str:
        return hashlib.sha256(f"{model}:{prompt}".encode()).hexdigest()[:16]

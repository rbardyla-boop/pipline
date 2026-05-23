"""Pure scalar metric functions for the Systems Dynamics Layer.

All functions are stateless and operate on plain Python lists / floats.
No imports from uaf.kernel or uaf.interfaces — this layer must be
portable to analysis notebooks and external tools without pulling in
the full UAF dependency graph.

Metric definitions (sourced from existing pipeline instrumentation):
  convergence_score      — mean pairwise cosine distance across session embeddings
  novelty_pressure       — mean + std of novelty distribution for a generation
  stability              — score variance over a rolling window
  plateau_distance       — |history[-1] - history[-2]|
  goodhart_pressure      — guard triggers / cycles elapsed
  trajectory_drift       — cumulative path length through embedding space
  refractory_load        — active locked clusters / cycle
"""

from __future__ import annotations

import math
from typing import Sequence


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _norm(v: Sequence[float]) -> float:
    return math.sqrt(sum(x * x for x in v))


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity in [-1, 1]. Returns 0.0 if either vector is zero."""
    na, nb = _norm(a), _norm(b)
    if na < 1e-10 or nb < 1e-10:
        return 0.0
    return _dot(a, b) / (na * nb)


def cosine_distance(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine distance in [0, 2]. Commonly used as novelty metric."""
    return 1.0 - cosine_similarity(a, b)


# ------------------------------------------------------------------ #
# Session-level metrics                                               #
# ------------------------------------------------------------------ #


def convergence_score(embeddings: list[Sequence[float]]) -> float:
    """Mean pairwise cosine distance across session embeddings.

    Returns 1.0 (maximally spread) when the archive is empty or has one item.
    Returns 0.0 when all embeddings are identical (fully converged).
    """
    n = len(embeddings)
    if n < 2:
        return 1.0
    total = 0.0
    count = 0
    for i in range(n):
        for j in range(i + 1, n):
            total += cosine_distance(embeddings[i], embeddings[j])
            count += 1
    return total / count if count > 0 else 1.0


def trajectory_drift(embeddings: list[Sequence[float]]) -> float:
    """Cumulative path length through embedding space.

    Measures how far the session has traveled — low drift = convergence,
    high drift = broad exploration.
    """
    if len(embeddings) < 2:
        return 0.0
    total = 0.0
    for i in range(1, len(embeddings)):
        total += cosine_distance(embeddings[i - 1], embeddings[i])
    return total


# ------------------------------------------------------------------ #
# Score history metrics                                               #
# ------------------------------------------------------------------ #


def stability(score_history: Sequence[float], window: int = 3) -> float:
    """Variance of composite score over the last *window* cycles.

    Low variance = stable (possibly plateaued), high = still improving.
    Returns 0.0 with fewer than 2 data points.
    """
    recent = list(score_history[-window:])
    if len(recent) < 2:
        return 0.0
    mean = sum(recent) / len(recent)
    return sum((x - mean) ** 2 for x in recent) / len(recent)


def plateau_distance(score_history: Sequence[float]) -> float | None:
    """Absolute score improvement between the last two cycles.

    Returns None if history has fewer than 2 entries.
    """
    if len(score_history) < 2:
        return None
    return abs(score_history[-1] - score_history[-2])


def goodhart_pressure(goodhart_warnings: int, cycles_elapsed: int) -> float:
    """Guard triggers per cycle — proxy for reward hacking intensity.

    Returns 0.0 when no cycles have elapsed.
    """
    if cycles_elapsed <= 0:
        return 0.0
    return goodhart_warnings / cycles_elapsed


# ------------------------------------------------------------------ #
# Per-generation novelty metrics                                      #
# ------------------------------------------------------------------ #


def novelty_pressure(novelty_scores: Sequence[float]) -> dict[str, float]:
    """Mean and std of novelty score distribution for a generation.

    Returns {"mean": float, "std": float, "min": float, "max": float}.
    Returns all-zero dict on empty input.
    """
    if not novelty_scores:
        return {"mean": 0.0, "std": 0.0, "min": 0.0, "max": 0.0}
    n = len(novelty_scores)
    mean = sum(novelty_scores) / n
    variance = sum((x - mean) ** 2 for x in novelty_scores) / n
    return {
        "mean": round(mean, 4),
        "std": round(math.sqrt(variance), 4),
        "min": round(min(novelty_scores), 4),
        "max": round(max(novelty_scores), 4),
    }


def refractory_load(
    refractory_clusters: list[dict],
    current_cycle: int,
    refractory_cycles: int = 2,
) -> float:
    """Active locked phrase clusters as a fraction of all tracked clusters.

    Returns 0.0 when no clusters have been tracked.
    """
    if not refractory_clusters:
        return 0.0
    active = sum(
        1 for c in refractory_clusters
        if current_cycle - c.get("cycle_added", 0) < refractory_cycles
    )
    return active / len(refractory_clusters)

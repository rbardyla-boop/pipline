"""Multi-cycle spatial computations — ports V5Simulator trajectory math as pure functions.

The V5Simulator.build_context() and update_session() methods in simulator.py
contain the core trajectory repulsion and decay logic. This module extracts
that math as pure, testable functions that operate on plain data structures
so the dynamics layer can consume it without importing the V5Simulator class.

All functions are stateless and dependency-free (no uaf.* imports needed).
"""

from __future__ import annotations

import math
from typing import Sequence


# ------------------------------------------------------------------ #
# Re-exports from metrics (so callers import from one place)          #
# ------------------------------------------------------------------ #

from uaf.dynamics.metrics import cosine_distance, convergence_score, trajectory_drift


# ------------------------------------------------------------------ #
# V5 trajectory math (ported from simulator.py)                      #
# ------------------------------------------------------------------ #

_DEFAULT_TRAJECTORY_THRESHOLD = 0.35  # avg pairwise distance below = converging
_DEFAULT_DECAY_RATE = 0.05


def session_converging(
    embeddings: list[Sequence[float]],
    threshold: float = _DEFAULT_TRAJECTORY_THRESHOLD,
) -> bool:
    """Return True if the session trajectory has converged (avg pairwise distance < threshold).

    Mirrors V5Simulator's trajectory repulsion check (simulator.py:62-78).
    Requires at least 3 embeddings; returns False otherwise.
    """
    if len(embeddings) < 3:
        return False
    score = convergence_score(embeddings)
    return score < threshold


def volatile_weights(
    n_cycles: int,
    current_cycle: int,
    decay_rate: float = _DEFAULT_DECAY_RATE,
) -> list[float]:
    """Compute per-cycle decay weights for *n_cycles* prior cycles.

    Weight formula: max(0.1, 1.0 - age * decay_rate)
    where age = current_cycle - cycle_index.

    Mirrors V5Simulator.build_context() volatile decay section.
    """
    weights = []
    for i in range(n_cycles):
        age = current_cycle - i
        w = max(0.1, 1.0 - age * decay_rate)
        weights.append(round(w, 4))
    return weights


def weighted_path_length(
    embeddings: list[Sequence[float]],
    current_cycle: int,
    decay_rate: float = _DEFAULT_DECAY_RATE,
) -> float:
    """Trajectory drift weighted by volatile decay.

    Later steps in the trajectory contribute more to the path length;
    older steps are down-weighted by the decay schedule. This gives a
    recency-sensitive measure of how much the session has been exploring.
    """
    if len(embeddings) < 2:
        return 0.0
    n = len(embeddings)
    total = 0.0
    for i in range(1, n):
        age = current_cycle - i
        weight = max(0.1, 1.0 - age * decay_rate)
        total += weight * cosine_distance(embeddings[i - 1], embeddings[i])
    return round(total, 6)


def trajectory_summary(
    embeddings: list[Sequence[float]],
    current_cycle: int,
    refractory_clusters: list[dict] | None = None,
    trajectory_warnings: int = 0,
    refractory_cycles: int = 2,
    threshold: float = _DEFAULT_TRAJECTORY_THRESHOLD,
) -> dict:
    """Return a full trajectory summary dict for the dynamics recorder.

    Keys:
        convergence_score:    float — mean pairwise cosine distance
        trajectory_drift:     float — cumulative path length
        weighted_drift:       float — decay-weighted path length
        session_converging:   bool  — True if below threshold
        trajectory_warnings:  int   — cumulative convergence events
        active_refractory:    int   — locked phrase cluster count
    """
    from uaf.dynamics.metrics import refractory_load

    active = 0
    if refractory_clusters is not None and refractory_clusters:
        frac = refractory_load(refractory_clusters, current_cycle, refractory_cycles)
        active = int(round(frac * len(refractory_clusters)))

    return {
        "convergence_score": round(convergence_score(embeddings), 6),
        "trajectory_drift": round(trajectory_drift(embeddings), 6),
        "weighted_drift": weighted_path_length(embeddings, current_cycle),
        "session_converging": session_converging(embeddings, threshold),
        "trajectory_warnings": trajectory_warnings,
        "active_refractory": active,
    }

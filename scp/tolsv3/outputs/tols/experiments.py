"""
tols/experiments.py
Importable experiment functions with timing wrappers.
"""

import time
import numpy as np
from typing import Dict
from .core import (
    TangentTOLS, make_orthogonal_patterns, make_random_patterns, corrupt
)

_N, _D = 32, 8
_FAITHFUL_THR = 0.95
_PASS_THR = 0.80


def _build(N, D, K, patterns, adaptive_K=True, seed=0):
    net = TangentTOLS(
        n_units=N, pattern_dim=D, coupling_strength=K,
        dt=0.005, coupling_rule="tensor_pseudo",
        adaptive_K=adaptive_K, seed=seed,
    )
    for p in patterns:
        net.store_pattern(p)
    return net


def run_faithful_rate(P, N=_N, D=_D, base_K=4.0, adaptive_K=True,
                      corruption=0.15, n_trials=10, max_patterns=8,
                      seed=42) -> Dict:
    """Measure faithful recall rate at a given pattern count P."""
    t0 = time.time()
    rng = np.random.RandomState(seed + P)
    try:
        patterns = make_orthogonal_patterns(P, N, D, rng)
    except ValueError as e:
        return {"P": P, "faithful_rate": 0.0, "error": str(e), "elapsed_s": 0}

    net = _build(N, D, base_K, patterns, adaptive_K=adaptive_K, seed=seed)
    faithful, total = 0, 0
    for pi in range(min(P, max_patterns)):
        target = patterns[pi]
        for trial in range(n_trials):
            tr = np.random.RandomState(seed + P * 10000 + pi * 100 + trial)
            cue = corrupt(target, corruption, tr)
            try:
                recalled, _, _ = net.recall(cue, max_steps=1000, tol=1e-5, log=False)
                if net.pattern_similarity(recalled, target) >= _FAITHFUL_THR:
                    faithful += 1
            except np.linalg.LinAlgError:
                pass
            total += 1
    return {
        "P": P,
        "faithful_rate": faithful / total if total > 0 else 0.0,
        "total_trials": total,
        "elapsed_s": time.time() - t0,
    }


def run_basin_radius(P, N=_N, D=_D, base_K=4.0, adaptive_K=True,
                     n_trials=20, seed=42) -> Dict:
    """Find the basin radius (max corruption with faithful ≥ 0.80) at pattern count P."""
    import numpy as _np
    t0 = time.time()
    rng = _np.random.RandomState(seed + P)
    try:
        patterns = make_orthogonal_patterns(P, N, D, rng)
    except ValueError as e:
        return {"P": P, "basin_radius": 0.0, "error": str(e), "elapsed_s": 0}

    net = _build(N, D, base_K, patterns, adaptive_K=adaptive_K, seed=seed)
    target = patterns[0]
    basin_radius = 0.0

    for corr in _np.arange(0.05, 0.95, 0.05):
        corr = round(float(corr), 2)
        faithful = 0
        for trial in range(n_trials):
            tr = _np.random.RandomState(seed + P * 100000 + int(corr * 1000) * 100 + trial)
            cue = corrupt(target, corr, tr)
            try:
                recalled, _, _ = net.recall(cue, max_steps=1000, tol=1e-5, log=False)
                if net.pattern_similarity(recalled, target) >= _FAITHFUL_THR:
                    faithful += 1
            except _np.linalg.LinAlgError:
                pass
        if faithful / n_trials >= _PASS_THR:
            basin_radius = corr

    return {
        "P": P,
        "basin_radius": basin_radius,
        "k_eff": base_K * N / P if adaptive_K else base_K,
        "elapsed_s": time.time() - t0,
    }

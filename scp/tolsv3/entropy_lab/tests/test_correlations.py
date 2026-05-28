"""
Falsification tests for entropy_lab.correlations.
"""

import sys
import types
from unittest.mock import patch

import numpy as np
import pytest

from entropy_lab import NonEquilibriumSandbox
from entropy_lab.correlations import (
    CorrelationLength,
    PairCorrelation,
    correlation_length,
    pair_correlation,
    sample_positions,
)


# ---------------------------------------------------------------------------
# Test 1: uniform random positions → G(r) ≈ 1 (normalisation validation)
# ---------------------------------------------------------------------------

def test_uniform_positions_g_approx_one():
    """After triangular-density normalisation, G(r) from uniform positions
    must be close to 1.0 across most bins.
    """
    rng = np.random.default_rng(0)
    n = 80
    n_snaps = 40
    snapshots = [rng.uniform(-1.0, 1.0, n) for _ in range(n_snaps)]

    pc = pair_correlation(snapshots, n_bins=30)

    # Exclude the first and last few bins (edge effects)
    interior = pc.g[3:-3]
    assert interior.mean() == pytest.approx(1.0, abs=0.35), (
        f"G(r) mean={interior.mean():.3f} not near 1.0 for uniform positions"
    )


# ---------------------------------------------------------------------------
# Test 2: two tight clusters → G(r) peaks at small r
# ---------------------------------------------------------------------------

def test_clustered_positions_peak_at_small_r():
    """Two tight clusters produce excess pairs at small distances → G(r) > 1
    near r=0.
    """
    rng = np.random.default_rng(1)
    n_snaps = 60
    snapshots = []
    for _ in range(n_snaps):
        cluster1 = rng.normal(-0.5, 0.05, 15)
        cluster2 = rng.normal(+0.5, 0.05, 15)
        snapshots.append(np.concatenate([cluster1, cluster2]))

    pc = pair_correlation(snapshots, n_bins=40)

    # G(r) should be > 1 near the intra-cluster distance scale (~0.1)
    small_r_mask = pc.r < 0.25
    assert pc.g[small_r_mask].max() > 1.0, (
        "G(r) never exceeded 1.0 at small r for two tight clusters"
    )


# ---------------------------------------------------------------------------
# Test 3: sample_positions determinism under fixed seed
# ---------------------------------------------------------------------------

def test_sample_positions_deterministic():
    """Two calls to sample_positions on the same sandbox with the same seed
    must return bitwise-identical snapshots.
    """
    sb = NonEquilibriumSandbox(
        n_agents=15, total_mass=150.0, kT_global=0.5, gamma=0.1,
        entropy_budget=30.0, seed=9, x_range=0.3,
    )

    snaps1 = sample_positions(sb, n_steps=50, sample_every=5, concept_force=0.3)
    snaps2 = sample_positions(sb, n_steps=50, sample_every=5, concept_force=0.3)

    assert len(snaps1) == len(snaps2)
    for i, (s1, s2) in enumerate(zip(snaps1, snaps2)):
        np.testing.assert_array_equal(s1, s2, err_msg=f"Snapshot {i} differs between calls")


# ---------------------------------------------------------------------------
# Test 4: log-linear fallback returns finite ξ with scipy removed
# ---------------------------------------------------------------------------

def test_loglinear_fallback_finite_xi():
    """correlation_length must fall back to log-linear OLS when scipy is
    unavailable and still return a finite ξ for clustered data.

    A single compact cluster at 0 is used so G(r)−1 is monotone-decreasing
    on the positive domain (small r), giving OLS slope < 0 → finite ξ.
    Two-cluster data creates a second G(r) peak at the inter-cluster distance
    which makes the OLS slope non-negative, forcing ξ → ∞.
    """
    rng = np.random.default_rng(2)
    n_snaps = 80
    # Single cluster: all agents near 0 with σ=0.15
    snapshots = [rng.normal(0.0, 0.15, 40) for _ in range(n_snaps)]
    pc = pair_correlation(snapshots, n_bins=40)

    # Monkeypatch scipy out of the module's import machinery
    import entropy_lab.correlations as corr_mod

    original_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else None

    # Patch by temporarily making the scipy import fail inside the function
    real_scipy = sys.modules.get("scipy", None)
    real_scipy_opt = sys.modules.get("scipy.optimize", None)
    try:
        sys.modules["scipy"] = None          # type: ignore[assignment]
        sys.modules["scipy.optimize"] = None  # type: ignore[assignment]

        result = correlation_length(pc)
    finally:
        if real_scipy is None:
            sys.modules.pop("scipy", None)
        else:
            sys.modules["scipy"] = real_scipy

        if real_scipy_opt is None:
            sys.modules.pop("scipy.optimize", None)
        else:
            sys.modules["scipy.optimize"] = real_scipy_opt

    assert np.isfinite(result.xi), f"Log-linear fallback returned non-finite ξ={result.xi}"
    assert result.method == "loglinear", f"Expected 'loglinear', got {result.method!r}"

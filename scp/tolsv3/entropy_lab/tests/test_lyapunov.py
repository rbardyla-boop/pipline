"""
Falsification tests for entropy_lab.lyapunov.

Each test probes a distinct dynamical regime where the expected sign or
magnitude of the maximum Lyapunov exponent is physically determined.
"""

import numpy as np
import pytest

from entropy_lab import NonEquilibriumSandbox
from entropy_lab.lyapunov import estimate_lyapunov


# ---------------------------------------------------------------------------
# Test 1: γ=0, no concept force — conservative Hamiltonian system
# ---------------------------------------------------------------------------

def test_conservative_lyapunov_finite():
    """With γ=0 and no concept force the system is conservative.

    λ_max must be finite and reasonably bounded.  For small initial positions
    (x_range=0.1) all pairs are attractive, the system behaves like a
    multi-dimensional oscillator, and |λ_max| should be small.
    """
    sb = NonEquilibriumSandbox(
        n_agents=10, total_mass=100.0, kT_global=0.0, gamma=0.0,
        entropy_budget=1e6, k_conf=2.0, seed=7, x_range=0.1,
    )
    result = estimate_lyapunov(sb, n_steps=200, concept_force=0.0, renorm_every=10)
    assert np.isfinite(result.max_lyapunov), "λ_max must be finite"
    assert abs(result.max_lyapunov) < 50.0, f"λ_max suspiciously large: {result.max_lyapunov}"


# ---------------------------------------------------------------------------
# Test 2: same seed → identical growth_log (shared-noise determinism)
# ---------------------------------------------------------------------------

def test_same_seed_identical_growth_log():
    """Two sandboxes with identical seed must produce bit-exact growth_log."""
    params = dict(
        n_agents=10, total_mass=100.0, kT_global=0.5, gamma=0.1,
        entropy_budget=20.0, k_conf=2.0, seed=42, x_range=0.5,
    )
    sb1 = NonEquilibriumSandbox(**params)
    sb2 = NonEquilibriumSandbox(**params)

    r1 = estimate_lyapunov(sb1, n_steps=100, concept_force=0.3, renorm_every=10)
    r2 = estimate_lyapunov(sb2, n_steps=100, concept_force=0.3, renorm_every=10)

    assert r1.growth_log == r2.growth_log, (
        "growth_log differs between identical-seed sandboxes — shared noise broken"
    )
    assert r1.max_lyapunov == r2.max_lyapunov


# ---------------------------------------------------------------------------
# Test 3: repulsion-dominant regime → λ_max > 0 (chaotic)
# ---------------------------------------------------------------------------

def test_repulsion_dominant_positive_lyapunov():
    """With x_range=1.0 many agent pairs are beyond the 0.8 attraction radius
    and repel each other.  With γ=0 the system is conservative and the
    repulsion cascade should produce positive λ_max (deterministic chaos).

    kT_global=0.5 (not 0) is required: with kT=0 the thermostat computes
    gamma/kT_i = 0/0 = NaN which propagates to momenta.
    """
    sb = NonEquilibriumSandbox(
        n_agents=20, total_mass=200.0, kT_global=0.5, gamma=0.0,
        entropy_budget=1e6, k_conf=2.0, seed=0, x_range=1.0,
    )
    result = estimate_lyapunov(sb, n_steps=300, concept_force=0.0, renorm_every=20)
    assert result.max_lyapunov > 0.0, (
        f"Expected λ_max > 0 in repulsion-dominant regime, got {result.max_lyapunov:.4f}"
    )


# ---------------------------------------------------------------------------
# Test 4: high-γ overdamped regime → λ_max < 0 (contracting)
# ---------------------------------------------------------------------------

def test_overdamped_negative_lyapunov():
    """With very high damping (γ=5) all trajectories converge;
    λ_max must be negative.
    """
    sb = NonEquilibriumSandbox(
        n_agents=10, total_mass=100.0, kT_global=0.1, gamma=5.0,
        entropy_budget=1e6, k_conf=10.0, seed=3, x_range=0.1,
    )
    result = estimate_lyapunov(sb, n_steps=300, concept_force=0.0, renorm_every=20)
    assert result.max_lyapunov < 0.0, (
        f"Expected λ_max < 0 in overdamped regime, got {result.max_lyapunov:.4f}"
    )

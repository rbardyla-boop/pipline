"""
Falsification tests for phi-series observables (Part XVI).
"""

import numpy as np
import pytest

from entropy_lab.observables import PhysicsTrace
from entropy_lab.scaling_observables import (
    BinderResult,
    binder_phi_cumulant,
    susceptibility_from_phi_trace,
)


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

def _make_trace_with_phi(phi_values: list[float]) -> PhysicsTrace:
    """Build a PhysicsTrace with prescribed phi_series (minimal x_mean etc.)."""
    trace = PhysicsTrace()
    for i, phi in enumerate(phi_values):
        trace.record(step=i, H=0.0, ep=0.0, mass_var=0.0, x_m=0.0, env=0.0)
        trace.record_phi(phi)
    return trace


# ---------------------------------------------------------------------------
# Test 1: frozen cluster (phi locked to +1) gives U_4 = 2/3 exactly
# ---------------------------------------------------------------------------

def test_binder_phi_frozen_cluster():
    """phi locked to +1 (FROZEN ordered phase) gives U_4 = 2/3 exactly.

    phi = +1 always: <phi^2> = 1, <phi^4> = 1 -> U_4 = 1 - 1/(3*1) = 2/3.
    """
    trace = _make_trace_with_phi([1.0] * 200)
    result = binder_phi_cumulant(trace, tail_fraction=1.0)
    assert abs(result.u4 - 2.0 / 3.0) < 1e-9, f"U_4 = {result.u4}, expected 2/3"
    assert abs(result.m2 - 1.0) < 1e-9, f"m2 = {result.m2}, expected 1.0"


# ---------------------------------------------------------------------------
# Test 2: symmetric Gaussian fluctuations give U_4 near 0
# ---------------------------------------------------------------------------

def test_binder_phi_gaussian_near_zero():
    """Gaussian phi fluctuations give U_4 near 0 (disordered phase value).

    Sample std(U_4) ~ 0.033 at n=10000, so tolerance 0.10 gives < 0.3% failure.
    """
    rng = np.random.default_rng(42)
    phi_vals = (rng.standard_normal(10_000) * 0.1).tolist()
    trace = _make_trace_with_phi(phi_vals)
    result = binder_phi_cumulant(trace, tail_fraction=1.0)
    assert abs(result.u4) < 0.10, f"U_4 = {result.u4:.4f}, expected near 0"


# ---------------------------------------------------------------------------
# Test 3: phi_series length matches n_steps after simulate_full()
# ---------------------------------------------------------------------------

def test_phi_series_length_matches_steps():
    """phi_series has exactly n_steps entries after simulate_full()."""
    from entropy_lab.thermodynamic_limit import DensityPreservingSandbox

    sb = DensityPreservingSandbox(
        n_agents=10,
        density=16.67,
        kT_global=0.5,
        gamma=0.1,
        entropy_budget=20.0,
        seed=0,
        ness_window=5,
    )
    _, trace = sb.simulate_full(n_steps=50, concept_force=0.3)
    assert len(trace.phi_series) == 50, (
        f"len(phi_series) = {len(trace.phi_series)}, expected 50"
    )


# ---------------------------------------------------------------------------
# Test 4: phi values are bounded in [-1, 1]
# ---------------------------------------------------------------------------

def test_phi_series_bounded():
    """phi = (M_right - M_left) / M_total must lie in [-1, 1] always."""
    from entropy_lab.thermodynamic_limit import DensityPreservingSandbox

    sb = DensityPreservingSandbox(
        n_agents=15,
        density=16.67,
        kT_global=0.5,
        gamma=0.1,
        entropy_budget=30.0,
        seed=1,
        ness_window=5,
    )
    _, trace = sb.simulate_full(n_steps=100, concept_force=0.3)
    phi = np.array(trace.phi_series)
    max_abs = float(np.abs(phi).max())
    assert max_abs <= 1.0 + 1e-9, f"phi out of range: max |phi| = {max_abs:.6f}"

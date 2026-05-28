"""
Falsification tests for entropy_lab.scaling_observables (Part XIV).
"""

import numpy as np
import pytest

from entropy_lab.observables import PhysicsTrace
from entropy_lab.scaling_observables import BinderResult, binder_cumulant, susceptibility_from_trace


def _make_trace(x_mean_values: list[float]) -> PhysicsTrace:
    """Build a minimal PhysicsTrace from a sequence of x_mean values."""
    trace = PhysicsTrace()
    for i, m in enumerate(x_mean_values):
        trace.record(step=i, H=0.0, ep=0.0, mass_var=0.0, x_m=m, env=0.0)
    return trace


# ---------------------------------------------------------------------------
# Test 1: Gaussian x_mean gives U_4 near 0
# ---------------------------------------------------------------------------

def test_gaussian_binder_near_zero():
    """Gaussian fluctuations must give U_4 near 0 (disordered phase value).

    For X ~ N(0,1): E[X^4] = 3 * E[X^2]^2, so U_4 = 0 exactly in expectation.
    Sample std(U_4) ~ 0.033 at n=10000, so tolerance 0.10 gives < 0.3% failure.
    """
    rng = np.random.default_rng(42)
    trace = _make_trace(rng.standard_normal(10_000).tolist())
    result = binder_cumulant(trace, tail_fraction=1.0)
    assert abs(result.u4) < 0.10, (
        f"Expected U_4 near 0 for Gaussian, got {result.u4:.4f}"
    )


# ---------------------------------------------------------------------------
# Test 2: Bimodal +/-1 gives U_4 near 2/3
# ---------------------------------------------------------------------------

def test_bimodal_binder_near_two_thirds():
    """Bimodal +-1 distribution must give U_4 near 2/3.

    <m^2> = 1, <m^4> = 1 -> U_4 = 1 - 1/(3*1) = 2/3.
    """
    values = [1.0 if i % 2 == 0 else -1.0 for i in range(500)]
    trace = _make_trace(values)
    result = binder_cumulant(trace, tail_fraction=1.0)
    assert abs(result.u4 - 2.0 / 3.0) < 0.01, (
        f"Expected U_4 near 2/3 for bimodal, got {result.u4:.6f}"
    )
    # Verify m2, m4 are correct
    assert abs(result.m2 - 1.0) < 1e-9
    assert abs(result.m4 - 1.0) < 1e-9


# ---------------------------------------------------------------------------
# Test 3: susceptibility scales exactly linearly with N
# ---------------------------------------------------------------------------

def test_susceptibility_linear_in_N():
    """chi = N * Var(m) must scale exactly linearly with N at fixed trace."""
    rng = np.random.default_rng(1)
    trace = _make_trace(rng.standard_normal(400).tolist())
    chi_10 = susceptibility_from_trace(trace, n_agents=10, tail_fraction=1.0)
    chi_20 = susceptibility_from_trace(trace, n_agents=20, tail_fraction=1.0)
    assert abs(chi_20 / chi_10 - 2.0) < 1e-9, (
        f"chi_20/chi_10 = {chi_20/chi_10:.9f}, expected exactly 2.0"
    )

"""
Falsification tests for entropy_lab.scaling_collapse (Part XVIII / Sprint 1).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from entropy_lab.observables import PhysicsTrace
from entropy_lab.scaling_collapse import (
    CollapseResult,
    compute_collapse,
    find_critical_density,
    mean_coupling_from_trace,
)


def _make_trace_with_mass_var(mass_var_values: list[float]) -> PhysicsTrace:
    trace = PhysicsTrace()
    for i, mv in enumerate(mass_var_values):
        trace.record(step=i, H=0.0, ep=0.0, mass_var=mv, x_m=0.0, env=0.0)
    return trace


# ---------------------------------------------------------------------------
# Test 1: Uniform mass → K_eff = M_total / N²
# ---------------------------------------------------------------------------

def test_mean_coupling_uniform_mass():
    """Var(mass) = 0 throughout: K_eff = M_total / N² (uniform-mass formula)."""
    trace = _make_trace_with_mass_var([0.0] * 200)
    n, M = 5, 10.0
    K_eff = mean_coupling_from_trace(trace, n_agents=n, M_total=M)
    expected = M / n ** 2   # 10/25 = 0.4
    assert abs(K_eff - expected) < 1e-9, f"K_eff={K_eff}, expected={expected}"


# ---------------------------------------------------------------------------
# Test 2: All mass concentrated on one agent → K_eff ≈ 0
# ---------------------------------------------------------------------------

def test_mean_coupling_concentrated_mass():
    """N=2, masses=[10, 0]: Var=25 → K_eff = M/N² - Var/(M*(N-1)) = 2.5 - 2.5 = 0."""
    n, M = 2, 10.0
    # masses = [10, 0]; mean=5; Var = ((10-5)² + (0-5)²)/2 = 25
    trace = _make_trace_with_mass_var([25.0] * 200)
    K_eff = mean_coupling_from_trace(trace, n_agents=n, M_total=M, tail_fraction=1.0)
    # K_eff = 10/4 - 25/(10*1) = 2.5 - 2.5 = 0.0
    assert abs(K_eff) < 1e-9, f"K_eff={K_eff}, expected=0.0"


# ---------------------------------------------------------------------------
# Test 3: Empty trace falls back to uniform-mass estimate
# ---------------------------------------------------------------------------

def test_mean_coupling_empty_trace_fallback():
    """Empty PhysicsTrace returns the uniform-mass estimate M/N²."""
    trace = PhysicsTrace()
    n, M = 10, 80.0
    K_eff = mean_coupling_from_trace(trace, n_agents=n, M_total=M)
    assert abs(K_eff - M / n ** 2) < 1e-9, f"K_eff={K_eff}, expected={M/n**2}"


# ---------------------------------------------------------------------------
# Test 4: find_critical_density locates the steepest-descent point
# ---------------------------------------------------------------------------

def test_find_critical_density_synthetic():
    """Lambda dropping steeply around density=7 gives rho_crit=7.0."""
    density = np.array([4.0, 6.0, 7.0, 8.0, 10.0, 15.0])
    lam     = np.array([1.0, 0.8, 0.3, 0.01, 0.05, 0.2])
    result = find_critical_density(lam, density)
    assert result is not None, "Expected a critical density, got None"
    rho_crit, lam_at_crit = result
    # np.gradient with non-uniform x: most negative at index 2 (density=7.0)
    assert abs(rho_crit - 7.0) < 1e-6, f"rho_crit={rho_crit}, expected=7.0"
    assert abs(lam_at_crit - 0.3) < 1e-9, f"lam_at_crit={lam_at_crit}, expected=0.3"


# ---------------------------------------------------------------------------
# Test 5: compute_collapse — perfect collapse returns quality = 1.0
# ---------------------------------------------------------------------------

def test_compute_collapse_perfect():
    """Identical scaled_rho at all kT → quality=1.0 and is_collapsed=True."""
    # scaled_rho = rho_crit * sqrt(kT/K_eff)
    # Choose K_eff=1.0, C=5.0: rho_crit = C/sqrt(kT) → scaled_rho = C for all kT
    K_eff = 1.0
    C = 5.0
    kT_values = [0.5, 1.0, 2.0, 4.0]
    raw = [(kT, C / math.sqrt(kT / K_eff), K_eff) for kT in kT_values]
    result = compute_collapse(raw, n_agents=10)
    assert abs(result.collapse_quality - 1.0) < 1e-9, (
        f"Expected quality=1.0, got {result.collapse_quality}"
    )
    assert result.is_collapsed(), "Perfect collapse should satisfy is_collapsed()"
    assert abs(result.mean_scaled_rho - C) < 1e-6, (
        f"Expected mean_scaled_rho={C}, got {result.mean_scaled_rho}"
    )
    assert result.std_scaled_rho < 1e-9, (
        f"Expected std=0.0, got {result.std_scaled_rho}"
    )

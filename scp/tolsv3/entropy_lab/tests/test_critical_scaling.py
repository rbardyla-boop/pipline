"""
Falsification tests for entropy_lab.critical_scaling (Part XV).
"""

import numpy as np
import pytest

from entropy_lab.critical_scaling import (
    BinderPoint,
    BinderSweep,
    binder_sweep,
    collapse_data,
    find_crossing,
    susceptibility_peak,
)


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

def _make_synthetic_sweep(
    n: int,
    kT_values: list[float],
    *,
    u4_values: list[float],
    chi_values: list[float],
) -> BinderSweep:
    """Build a BinderSweep from prescribed u4 and chi values (no simulation)."""
    points = [
        BinderPoint(
            kT=kT, u4=u4, chi=chi, ep_per_agent=0.0,
            lambda_max=0.0, phase="NESS", error=None,
        )
        for kT, u4, chi in zip(kT_values, u4_values, chi_values)
    ]
    return BinderSweep(
        n_agents=n, density=16.67, kT_values=list(kT_values),
        points=points, gamma=0.1, n_steps=0,
    )


# ---------------------------------------------------------------------------
# Test 1: find_crossing identifies exact crossing of two linear U_4 curves
# ---------------------------------------------------------------------------

def test_find_crossing_exact():
    """find_crossing correctly identifies the crossing of two monotone U_4 curves.

    u4_10 = 0.6 - 0.4*kT
    u4_20 = 0.8 - 0.6*kT
    Analytical crossing: 0.6 - 0.4*kT = 0.8 - 0.6*kT  →  0.2*kT = 0.2  →  kT = 1.0.
    """
    kT_values = list(np.linspace(0.5, 1.5, 21))
    s10 = _make_synthetic_sweep(
        10, kT_values,
        u4_values=[0.6 - 0.4 * k for k in kT_values],
        chi_values=[1.0] * 21,
    )
    s20 = _make_synthetic_sweep(
        20, kT_values,
        u4_values=[0.8 - 0.6 * k for k in kT_values],
        chi_values=[1.0] * 21,
    )
    crossing = find_crossing([s10, s20])
    assert crossing is not None, "Expected a crossing but find_crossing returned None"
    assert abs(crossing.kT_c - 1.0) < 0.05, (
        f"kT_c = {crossing.kT_c:.4f}, expected 1.0 ± 0.05"
    )
    assert 0.0 < crossing.u4_c < 1.0, (
        f"u4_c = {crossing.u4_c:.4f} outside (0, 1)"
    )


def test_find_crossing_returns_none_when_absent():
    """find_crossing returns None when curves do not cross in the kT range."""
    kT_values = list(np.linspace(0.5, 1.5, 11))
    # u4_10 always above u4_20 — no crossing
    s10 = _make_synthetic_sweep(
        10, kT_values,
        u4_values=[0.5 - 0.1 * k for k in kT_values],
        chi_values=[1.0] * 11,
    )
    s20 = _make_synthetic_sweep(
        20, kT_values,
        u4_values=[0.4 - 0.1 * k for k in kT_values],
        chi_values=[1.0] * 11,
    )
    crossing = find_crossing([s10, s20])
    assert crossing is None, f"Expected None but got {crossing}"


# ---------------------------------------------------------------------------
# Test 2: susceptibility_peak returns kT at known maximum
# ---------------------------------------------------------------------------

def test_susceptibility_peak_correct():
    """susceptibility_peak returns the kT and chi value at the chi maximum."""
    kT_values = [0.5, 0.75, 1.0, 1.25, 1.5]
    chi_values = [0.1, 0.5, 2.0, 0.5, 0.1]
    sweep = _make_synthetic_sweep(
        10, kT_values,
        u4_values=[0.3] * 5, chi_values=chi_values,
    )
    kT_peak, chi_peak = susceptibility_peak(sweep)
    assert abs(kT_peak - 1.0) < 1e-9, f"kT_peak = {kT_peak}, expected 1.0"
    assert abs(chi_peak - 2.0) < 1e-9, f"chi_peak = {chi_peak}, expected 2.0"


def test_susceptibility_peak_all_nan():
    """susceptibility_peak returns (nan, nan) when all chi values are nan."""
    kT_values = [0.5, 1.0, 1.5]
    points = [
        BinderPoint(kT=k, u4=float("nan"), chi=float("nan"),
                    ep_per_agent=float("nan"), lambda_max=float("nan"),
                    phase="ERROR", error="synthetic error")
        for k in kT_values
    ]
    sweep = BinderSweep(n_agents=10, density=16.67, kT_values=kT_values,
                        points=points, gamma=0.1, n_steps=0)
    kT_peak, chi_peak = susceptibility_peak(sweep)
    assert np.isnan(kT_peak) and np.isnan(chi_peak)


# ---------------------------------------------------------------------------
# Test 3: collapse_data produces zero residual for exact FSS model
# ---------------------------------------------------------------------------

def test_collapse_exact_scaling():
    """collapse_data is exact for chi(kT, N) = N^(γ/ν) / (1 + ((kT-Tc)*N^(1/ν))^2).

    With Tc=1.0, γ/ν=1.0, 1/ν=1.0:
      x_i = (kT_i - 1.0) * N
      y_i = chi_i / N = 1 / (1 + x_i^2)

    So y_collapsed = 1/(1 + x_collapsed^2) exactly, to machine precision.
    """
    kT_values = list(np.linspace(0.5, 1.5, 21))
    Tc, gn, onu = 1.0, 1.0, 1.0
    sweeps = []
    for n in [5, 10, 20]:
        chi_vals = [
            float(n ** gn) / (1.0 + ((k - Tc) * float(n ** onu)) ** 2)
            for k in kT_values
        ]
        sweeps.append(_make_synthetic_sweep(
            n, kT_values,
            u4_values=[0.3] * 21,
            chi_values=chi_vals,
        ))
    x, y, _ = collapse_data(sweeps, Tc, gn, onu)
    y_expected = 1.0 / (1.0 + x ** 2)
    np.testing.assert_allclose(
        y, y_expected, atol=1e-10,
        err_msg="Data collapse is not exact for known FSS model",
    )


# ---------------------------------------------------------------------------
# Test 4: binder_sweep structural integrity (live, fast)
# ---------------------------------------------------------------------------

def test_binder_sweep_structure():
    """binder_sweep returns a BinderSweep with correct metadata and bounded U_4."""
    kT_values = [0.3, 0.5, 1.0]
    sweep = binder_sweep(
        n_agents=10, kT_values=kT_values, density=16.67,
        n_steps=60, ness_window=5, lyapunov_steps=30,
    )
    assert sweep.n_agents == 10
    assert sweep.kT_values == kT_values
    assert len(sweep.points) == 3
    for pt in sweep.points:
        if pt.error is None:
            assert -2.0 < pt.u4 < 2.0, (
                f"U_4 = {pt.u4:.4f} at kT={pt.kT} is outside physical range [-2, 2]"
            )
            assert pt.chi >= 0.0, (
                f"chi = {pt.chi:.4f} at kT={pt.kT} is negative"
            )

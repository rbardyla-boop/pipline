"""
Falsification tests for entropy_lab.topology (Part XIII).
"""

import numpy as np
import pytest

from entropy_lab import NonEquilibriumSandbox
from entropy_lab.topology import (
    AllToAllKernel,
    ExponentialKernel,
    GaussianKernel,
    HardCutoffKernel,
    LocalizedSandbox,
)


# ---------------------------------------------------------------------------
# Test 1: AllToAllKernel returns a ones matrix
# ---------------------------------------------------------------------------

def test_alltoall_kernel_returns_ones():
    """AllToAllKernel must return np.ones_like(dist) for any input shape."""
    dist = np.array([[0.0, 0.3, 0.9], [0.3, 0.0, 0.5], [0.9, 0.5, 0.0]])
    k = AllToAllKernel()(dist)
    np.testing.assert_array_equal(k, np.ones((3, 3)))


# ---------------------------------------------------------------------------
# Test 2: ExponentialKernel is monotone-decreasing in distance
# ---------------------------------------------------------------------------

def test_exponential_kernel_monotone_decreasing():
    """ExponentialKernel must be strictly decreasing as distance increases."""
    r = np.linspace(0.0, 2.0, 100)
    k = ExponentialKernel(xi=0.3)(r.reshape(1, -1)).ravel()
    assert (np.diff(k) < 0).all(), "ExponentialKernel must be strictly decreasing"


# ---------------------------------------------------------------------------
# Test 3: HardCutoffKernel zeros all interactions beyond radius
# ---------------------------------------------------------------------------

def test_hardcutoff_kernel_zeros_beyond_radius():
    """HardCutoffKernel must be 1.0 at or within radius and 0.0 beyond."""
    rng = np.random.default_rng(0)
    dist = rng.uniform(0.0, 2.0, (20, 20))
    radius = 0.4
    k = HardCutoffKernel(radius=radius)(dist)
    assert (k[dist > radius] == 0.0).all()
    assert (k[dist <= radius] == 1.0).all()


# ---------------------------------------------------------------------------
# Test 4: LocalizedSandbox with AllToAllKernel reproduces NonEquilibriumSandbox
# ---------------------------------------------------------------------------

def test_alltoall_reproduces_original():
    """LocalizedSandbox(AllToAllKernel) must give bitwise-identical results.

    AllToAllKernel multiplies K by ones_like(dist), which is exact in IEEE 754,
    so every floating-point operation in the loop is identical to the original.
    """
    params = dict(
        n_agents=12, total_mass=96.0, kT_global=0.5, gamma=0.1,
        entropy_budget=24.0, seed=3, x_range=0.3,
    )
    r_orig = NonEquilibriumSandbox(**params).simulate(n_steps=50, concept_force=0.4)
    r_loc = LocalizedSandbox(**params, kernel=AllToAllKernel()).simulate(
        n_steps=50, concept_force=0.4,
    )

    assert r_orig.entropy_production_rate == pytest.approx(
        r_loc.entropy_production_rate, rel=1e-10
    )
    assert r_orig.phase_state == r_loc.phase_state
    assert r_orig.survivability == pytest.approx(r_loc.survivability, rel=1e-10)

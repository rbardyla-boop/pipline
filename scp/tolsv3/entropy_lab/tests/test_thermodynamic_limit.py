"""
Falsification tests for entropy_lab.thermodynamic_limit (Part XIV).
"""

import numpy as np
import pytest

from entropy_lab.thermodynamic_limit import (
    DensityPreservingSandbox,
    _periodic_distance,
    _wrap_periodic,
)


# ---------------------------------------------------------------------------
# Test 1: box_length = N / density for two different N values
# ---------------------------------------------------------------------------

def test_density_constant_across_N():
    """box_length must equal N / density; density must be constant across N."""
    density = 16.67
    for n in (10, 20):
        sb = DensityPreservingSandbox(
            n_agents=n, density=density,
            kT_global=0.5, gamma=0.1,
            entropy_budget=2.0 * n, seed=0,
        )
        assert abs(sb.box_length - n / density) < 1e-9, (
            f"N={n}: box_length={sb.box_length:.6f}, expected {n/density:.6f}"
        )
        assert abs(n / sb.box_length - density) < 1e-6, (
            f"N={n}: computed density={n/sb.box_length:.4f}, expected {density}"
        )


# ---------------------------------------------------------------------------
# Test 2: positions stay within [-L/2, L/2] after simulate
# ---------------------------------------------------------------------------

def test_positions_wrapped_after_simulate():
    """Periodic wrapping must keep all positions in [-L/2, L/2]."""
    sb = DensityPreservingSandbox(
        n_agents=15, density=16.67,
        kT_global=0.5, gamma=0.1,
        entropy_budget=30.0, seed=0, ness_window=10,
    )
    sb.simulate(n_steps=100, concept_force=0.4)
    x = sb.manifold.x
    L = sb.box_length
    assert (np.abs(x) <= L / 2.0 + 1e-9).all(), (
        f"Position out of bounds: max|x|={np.abs(x).max():.6f}, L/2={L/2:.6f}"
    )


# ---------------------------------------------------------------------------
# Test 3: periodic distance satisfies minimum-image expected values
# ---------------------------------------------------------------------------

def test_periodic_distance_minimum_image():
    """_periodic_distance must return the minimum-image toroidal distance."""
    x = np.array([0.0, 0.8, -0.8])
    L = 2.0
    dist = _periodic_distance(x, L)

    # d(0, 0.8) = min(0.8, 1.2) = 0.8
    assert abs(dist[0, 1] - 0.8) < 1e-12

    # d(0.8, -0.8): raw = 1.6, L - 1.6 = 0.4 -> periodic = 0.4
    assert abs(dist[1, 2] - 0.4) < 1e-12

    # self-distance = 0
    assert (np.diag(dist) == 0.0).all()

    # symmetry
    np.testing.assert_array_equal(dist, dist.T)


# ---------------------------------------------------------------------------
# Test 4: _coupling is invariant under global position shift by L
# ---------------------------------------------------------------------------

def test_coupling_periodic_translation_invariant():
    """Shifting all positions by one box length must not change the coupling."""
    mass = np.ones(6) * 2.0
    x = np.linspace(-0.25, 0.25, 6)
    sb = DensityPreservingSandbox(
        n_agents=6, density=6.0,
        kT_global=0.5, gamma=0.1,
        entropy_budget=12.0, seed=7,
    )
    k1 = sb._coupling(mass, x)
    k2 = sb._coupling(mass, x + sb.box_length)
    np.testing.assert_allclose(k1, k2, atol=1e-10,
                               err_msg="Coupling changed under position shift by L")

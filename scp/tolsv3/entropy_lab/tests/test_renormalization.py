"""
Falsification tests for entropy_lab.renormalization.
"""

import numpy as np

from entropy_lab.renormalization import IntensiveRedistributor, RenormalizedSandbox


# ---------------------------------------------------------------------------
# Test 1: bleed_rate=0 → no mass transfer
# ---------------------------------------------------------------------------

def test_zero_bleed_rate_no_transfer():
    """With bleed_rate=0, total_transfer=0 and mass must be unchanged."""
    rng = np.random.default_rng(0)
    mass = rng.uniform(1.0, 10.0, 20)
    p = rng.standard_normal(20)
    rd = IntensiveRedistributor(bleed_rate=0.0)
    new_mass = rd.redistribute(mass, p, mass.mean())
    np.testing.assert_allclose(new_mass, mass)


# ---------------------------------------------------------------------------
# Test 2: total agent mass conserved over 100 simulation steps
# ---------------------------------------------------------------------------

def test_mass_conservation_over_simulation():
    """Total agent mass must be conserved to within floating-point tolerance."""
    sb = RenormalizedSandbox(
        n_agents=15, total_mass=120.0, kT_global=0.5, gamma=0.1,
        entropy_budget=30.0, seed=7,
    )
    m0 = float(sb.manifold._mass.sum())
    sb.simulate(n_steps=100, concept_force=0.3)
    m1 = float(sb.manifold._mass.sum())
    assert abs(m1 - m0) / m0 < 1e-5, f"Mass drift: {abs(m1 - m0) / m0:.2e}"


# ---------------------------------------------------------------------------
# Test 3: gradient direction — fast agent absorbs, slow agent bleeds
# ---------------------------------------------------------------------------

def test_gradient_direction():
    """Fast agent gains mass; slow agent loses mass."""
    mass = np.array([5.0, 5.0])
    p = np.array([10.0, 0.001])
    rd = IntensiveRedistributor(bleed_rate=0.5)
    new_mass = rd.redistribute(mass, p, mass.mean())
    assert new_mass[0] > mass[0], "fast agent should gain mass"
    assert new_mass[1] < mass[1], "slow agent should lose mass"


# ---------------------------------------------------------------------------
# Test 4: env_mass unchanged (intensive redistribution is agent-to-agent only)
# ---------------------------------------------------------------------------

def test_env_mass_unchanged():
    """Intensive redistribution moves mass among agents only; env_mass must
    not change. This distinguishes it from the original, which bleeds mass
    to and from the environment reservoir.

    Also verifies that the redistribution patch is cleaned up from the
    manifold instance dict after simulate() returns.
    """
    sb = RenormalizedSandbox(
        n_agents=15, total_mass=120.0, kT_global=0.5, gamma=0.1,
        entropy_budget=30.0, seed=5,
    )
    env0 = sb.manifold.env_mass
    assert "redistribute_mass" not in sb.manifold.__dict__, (
        "no instance attribute before simulate()"
    )

    sb.simulate(n_steps=100, concept_force=0.3)

    env1 = sb.manifold.env_mass
    assert abs(env1 - env0) < 1e-6, (
        f"env_mass must not change: {env0:.8f} → {env1:.8f}"
    )
    assert "redistribute_mass" not in sb.manifold.__dict__, (
        "instance attribute must be deleted after simulate()"
    )

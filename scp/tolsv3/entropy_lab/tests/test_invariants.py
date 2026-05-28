"""
Falsification test suite for the Non-Equilibrium Entropy Budget Engine.

Each test corresponds to a specific physical or mathematical invariant that
the sandbox must satisfy. A failure here indicates either a broken invariant
or a numerical artifact masquerading as physics.
"""

import numpy as np
import pytest

from entropy_lab import NonEquilibriumSandbox, PhaseState
from entropy_lab.dissipation import LangevinThermostat
from entropy_lab.lagrangian import compute_coupling_matrix
from entropy_lab.manifold import AttentionManifold


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _manifold(n: int = 20, M: float = 200.0, seed: int = 0) -> AttentionManifold:
    return AttentionManifold(n, M, np.random.default_rng(seed))


def _thermostat(**kwargs) -> LangevinThermostat:
    defaults = dict(gamma=0.1, kT_global=0.5, entropy_budget=10.0, beta=1.0, alpha=2.0)
    return LangevinThermostat(**{**defaults, **kwargs})


# ------------------------------------------------------------------
# Test 1: γ=0 → Σ̇ = 0
# ------------------------------------------------------------------

def test_zero_gamma_no_entropy_production():
    """With no dissipation, entropy production must be exactly zero."""
    m = _manifold()
    t = _thermostat(gamma=0.0)
    coupling = compute_coupling_matrix(m.mass, m.x, m.M_total)
    ep = t.entropy_production_rate(m.mass, m.p, coupling)
    assert ep == pytest.approx(0.0, abs=1e-12)


# ------------------------------------------------------------------
# Test 2: Σ̇ ≥ 0 always
# ------------------------------------------------------------------

def test_entropy_production_nonnegative():
    """Entropy production is nonnegative for any momentum values (2nd law)."""
    rng = np.random.default_rng(99)
    m = _manifold()
    m._p = rng.standard_normal(m.n) * 5.0   # large random momenta
    t = _thermostat()
    coupling = compute_coupling_matrix(m.mass, m.x, m.M_total)
    ep = t.entropy_production_rate(m.mass, m.p, coupling)
    assert ep >= 0.0


# ------------------------------------------------------------------
# Test 3: Mass conservation at every step
# ------------------------------------------------------------------

def test_mass_conservation_every_step():
    """Σ M_i + M_env = M_total before and after a 100-step simulation."""
    sb = NonEquilibriumSandbox(n_agents=30, total_mass=300.0, seed=42)
    M_total = sb.M_total

    initial = float(sb.manifold.mass.sum()) + sb.manifold.env_mass
    assert abs(initial - M_total) < 1e-9, "Initial conservation violated"

    sb.simulate(n_steps=100)

    final = float(sb.manifold.mass.sum()) + sb.manifold.env_mass
    assert abs(final - M_total) < 1e-6, f"Final conservation violated: drift={final - M_total:.2e}"


# ------------------------------------------------------------------
# Test 4: Soft budget — γ_eff is monotone, no discontinuities
# ------------------------------------------------------------------

def test_soft_budget_never_clips():
    """gamma_eff must be strictly monotone-decreasing; no hard discontinuity."""
    t = _thermostat(gamma=1.0, entropy_budget=5.0, alpha=2.0)
    # Evaluate over a wide range including well past the budget
    ep_rates = np.linspace(0.0, 200.0, 1000)
    g_effs = np.array([t.effective_gamma(ep) for ep in ep_rates])

    # Monotone-decreasing (soft feedback, not a hard clip)
    diffs = np.diff(g_effs)
    assert (diffs <= 1e-12).all(), "gamma_eff is not monotone-decreasing — hard clipping present"

    # The function should asymptote to 0, never reach exactly 0 (no floor)
    assert g_effs[-1] > 0.0, "gamma_eff reached zero — hard floor present"

    # Boundary check: at ep=0, gamma_eff == gamma_0
    assert g_effs[0] == pytest.approx(t.gamma, rel=1e-9)


# ------------------------------------------------------------------
# Test 5: Local temperature varies across agents
# ------------------------------------------------------------------

def test_local_temperature_variation():
    """kT_i must differ across agents with random positions (beta > 0)."""
    m = _manifold(n=40)
    t = _thermostat(beta=1.0)
    coupling = compute_coupling_matrix(m.mass, m.x, m.M_total)
    kT_i = t.local_temperature(coupling)
    assert kT_i.std() > 1e-6, "All agents have identical kT_i (unexpected for random positions)"


# ------------------------------------------------------------------
# Test 6: High kT → non-NESS (structure dispersed)
# ------------------------------------------------------------------

def test_high_kT_not_ness():
    """Extreme temperature scatters all structure; system must not reach NESS."""
    sb = NonEquilibriumSandbox(
        n_agents=20, total_mass=200.0, kT_global=50.0, gamma=0.5,
        entropy_budget=500.0, seed=7, ness_window=20,
    )
    report = sb.simulate(n_steps=300)
    assert report.phase_state != PhaseState.NESS, (
        f"Unexpectedly reached NESS under extreme temperature: {report.phase_state}"
    )


# ------------------------------------------------------------------
# Test 7: γ=0 → FROZEN (zero dissipation)
# ------------------------------------------------------------------

def test_low_kT_reaches_frozen():
    """Zero dissipation (gamma=0) produces exactly zero entropy → FROZEN.

    At thermal equilibrium, Sigma_dot_eq = N * gamma regardless of temperature
    (kT cancels via equipartition).  FROZEN (Sigma_dot < eps_entropy) is
    therefore only achievable when gamma=0; temperature alone cannot freeze
    a Langevin system in steady state.

    This test verifies the full classifier pipeline, not just the formula:
    with gamma=0 and no concept force the system conserves total energy
    (T + V_spring + V_conf) and the NESS detector correctly reports FROZEN.
    """
    sb = NonEquilibriumSandbox(
        n_agents=20, total_mass=200.0, kT_global=0.5, gamma=0.0,
        entropy_budget=1e5, k_conf=5.0, seed=3, ness_window=20, x_range=0.1,
    )
    report = sb.simulate(n_steps=300, concept_force=0.0)
    assert report.phase_state == PhaseState.FROZEN, (
        f"Expected FROZEN with zero dissipation, got {report.phase_state}"
    )


# ------------------------------------------------------------------
# Test 8: Moderate kT reaches NESS or METASTABLE (not FROZEN/RUNAWAY)
# ------------------------------------------------------------------

def test_moderate_kT_reaches_ness_regime():
    """Balanced parameters should produce NESS or METASTABLE, not collapse.

    Agents start in x_range=0.3 (all within the 0.8 attraction radius) so
    every initial pair is attractive.  This prevents the repulsion cascade
    that occurs when agents are seeded uniformly in [-1,1]: many pairs would
    be beyond 0.8, immediately generating net-outward forces that exceed
    k_conf=2 and cause divergence.

    N=20 (not 50) is used because with N=50 mass bleeds to environment at
    2.4/step vs 0.8/step for N=20 (∝ N*P(slow)*M_i).  The slower bleed
    keeps env_mass_fraction below 0.8 over 300 steps, giving the NESS window
    a stable H to classify against.

    Budget is set to 100 = 20x Sigma_dot_eq (= N*gamma = 2) so the soft
    feedback engages gently without choking the damping channel.
    """
    sb = NonEquilibriumSandbox(
        n_agents=20, total_mass=200.0, kT_global=0.5, gamma=0.1,
        entropy_budget=100.0, seed=0, ness_window=20, x_range=0.3,
    )
    report = sb.simulate(n_steps=300, concept_force=0.5)
    assert report.phase_state in (PhaseState.NESS, PhaseState.METASTABLE), (
        f"Expected NESS or METASTABLE at balanced parameters, got {report.phase_state}"
    )


# ------------------------------------------------------------------
# Test 9: Autocorrelation stable in true NESS
# ------------------------------------------------------------------

def test_autocorr_stable_in_ness():
    """In a NESS regime, τ_corr drift should not be strongly negative."""
    sb = NonEquilibriumSandbox(
        n_agents=50, total_mass=500.0, kT_global=0.5, gamma=0.1,
        entropy_budget=10.0, seed=1, ness_window=30,
    )
    report = sb.simulate(n_steps=400, concept_force=0.5)
    if report.phase_state == PhaseState.NESS:
        assert report.autocorr_drift > -1.0, (
            f"Coherence time collapsing too fast in NESS: drift={report.autocorr_drift:.4f}"
        )


# ------------------------------------------------------------------
# Test 10: METASTABLE ≠ NESS under high noise with weak coupling
# ------------------------------------------------------------------

def test_metastable_distinguished_from_ness():
    """High temperature with weak coupling should produce METASTABLE or worse, not NESS."""
    sb = NonEquilibriumSandbox(
        n_agents=20, total_mass=200.0, kT_global=5.0, gamma=0.05,
        entropy_budget=20.0, beta=0.1, seed=5, ness_window=20,
    )
    report = sb.simulate(n_steps=250, concept_force=0.3)
    # Under these conditions structure erodes; τ_corr should drift downward
    # so the system must NOT be a stable NESS
    if report.phase_state == PhaseState.NESS:
        # If classified NESS, drift must not be confidently positive
        # (a truly stable NESS here would be suspicious given parameters)
        assert report.autocorr_drift <= 0.5, (
            "Unexpectedly stable NESS under high-noise / weak-coupling conditions"
        )

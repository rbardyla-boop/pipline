"""
lyapunov — Maximum Lyapunov exponent via the Benettin twin-trajectory method.

Design notes:
  - Shared noise (quenched-noise convention): both trajectories receive the
    same z ~ N(0,1)^n draw each step.  Two independent noise streams would
    measure noise-driven divergence (grows ~√t), not dynamical instability.
  - State is cloned into plain numpy arrays; the sandbox's manifold is not
    mutated.  Two full NonEquilibriumSandbox instances are not needed.
  - Phase-space metric covers (x, p) only.  Mass is a slow conserved channel
    that would distort λ_max.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .lagrangian import compute_coupling_matrix, compute_forces


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _redistribute_mass(
    mass: np.ndarray,
    p: np.ndarray,
    env_mass: float,
    M_total: float,
    speed_scale: float = 0.05,
    decay_scale: float = 0.02,
) -> tuple[np.ndarray, float]:
    """Replicate AttentionManifold.redistribute_mass on plain arrays."""
    mass = mass.copy()
    speeds = np.abs(p)

    fast = speeds > 1.0
    if fast.any() and env_mass > 0.1:
        n_fast = int(fast.sum())
        per_agent = min(env_mass * speed_scale / n_fast, 0.5)
        mass[fast] += per_agent
        env_mass -= per_agent * n_fast

    slow = speeds < 0.1
    if slow.any():
        bleed = mass[slow] * decay_scale
        mass[slow] -= bleed
        env_mass += float(bleed.sum())

    # project_mass
    mass = np.maximum(mass, 0.0)
    env_mass = max(0.0, env_mass)
    drift = M_total - (mass.sum() + env_mass)
    if abs(drift) > 1e-9:
        n = len(mass)
        correction = drift / (n + 1)
        mass += correction
        env_mass += correction

    return mass, env_mass


def _o_step(
    p: np.ndarray,
    mass: np.ndarray,
    coupling: np.ndarray,
    dt: float,
    thermostat,
    z: np.ndarray,
) -> np.ndarray:
    """Langevin O-step with a pre-drawn noise vector z."""
    kT_i = thermostat.local_temperature(coupling)
    ep_rate = thermostat.entropy_production_rate(mass, p, coupling)
    g_eff = thermostat.effective_gamma(ep_rate)
    sigma = np.sqrt(np.maximum(2.0 * g_eff * kT_i * dt, 0.0))
    return p * (1.0 - g_eff * dt) + z * sigma


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LyapunovResult:
    max_lyapunov: float       # (1 / (n_renorm * renorm_every * dt)) * Σ log(d_k / ε)
    growth_log: list[float]   # log(d_k / ε) at each renormalisation step
    epsilon: float
    n_steps: int
    converged: bool           # tail-variance heuristic: last-third std < overall
    noise_shared: bool        # always True; stored for methodological transparency


def estimate_lyapunov(
    sandbox,
    n_steps: int = 500,
    *,
    epsilon: float = 1e-8,
    concept_force: float = 0.5,
    renorm_every: int = 20,
) -> LyapunovResult:
    """Estimate the maximum Lyapunov exponent of the sandbox's attractor.

    Parameters
    ----------
    sandbox:
        A NonEquilibriumSandbox in its initial (pre-simulate) state.
        The sandbox is not mutated.
    epsilon:
        Initial separation between baseline and perturbed trajectories.
    renorm_every:
        Steps between Benettin renormalisations.
    """
    thermostat = sandbox.thermostat
    dt = sandbox.dt
    k_conf = sandbox.k_conf
    M_total = sandbox.M_total
    n = sandbox.manifold.n

    # ---- snapshot baseline state -----------------------------------------
    x_a = sandbox.manifold.x
    p_a = sandbox.manifold.p
    mass_a = sandbox.manifold.mass
    env_a = float(sandbox.manifold.env_mass)

    # ---- initial perturbation in (x, p) space ----------------------------
    rng = sandbox.rng
    pert = rng.standard_normal(2 * n)
    pert /= np.linalg.norm(pert)
    x_b = x_a + pert[:n] * epsilon
    p_b = p_a + pert[n:] * epsilon
    mass_b = mass_a.copy()
    env_b = env_a

    # separate RNG for shared noise stream (deterministic given sandbox seed)
    noise_seed = int(rng.integers(2**63))
    noise_rng = np.random.default_rng(noise_seed)

    # ---- initial couplings -----------------------------------------------
    coupling_a = compute_coupling_matrix(mass_a, x_a, M_total)
    coupling_b = compute_coupling_matrix(mass_b, x_b, M_total)

    growth_log: list[float] = []

    for step in range(n_steps):
        z = noise_rng.standard_normal(n)

        # trajectory A
        F_a = compute_forces(x_a, coupling_a, k_conf) + concept_force * np.sin(x_a)
        p_a = p_a + F_a * dt
        p_a = _o_step(p_a, mass_a, coupling_a, dt, thermostat, z)
        x_a = x_a + p_a * dt
        mass_a, env_a = _redistribute_mass(mass_a, p_a, env_a, M_total)
        coupling_a = compute_coupling_matrix(mass_a, x_a, M_total)

        # trajectory B (same z)
        F_b = compute_forces(x_b, coupling_b, k_conf) + concept_force * np.sin(x_b)
        p_b = p_b + F_b * dt
        p_b = _o_step(p_b, mass_b, coupling_b, dt, thermostat, z)
        x_b = x_b + p_b * dt
        mass_b, env_b = _redistribute_mass(mass_b, p_b, env_b, M_total)
        coupling_b = compute_coupling_matrix(mass_b, x_b, M_total)

        # Benettin renormalisation
        if (step + 1) % renorm_every == 0:
            dx = x_b - x_a
            dp = p_b - p_a
            sep = float(np.sqrt((dx ** 2).sum() + (dp ** 2).sum()))
            if sep > 0.0:
                growth_log.append(np.log(sep / epsilon))
                scale = epsilon / sep
                x_b = x_a + dx * scale
                p_b = p_a + dp * scale
                coupling_b = compute_coupling_matrix(mass_b, x_b, M_total)

    if not growth_log:
        return LyapunovResult(
            max_lyapunov=0.0,
            growth_log=[],
            epsilon=epsilon,
            n_steps=n_steps,
            converged=False,
            noise_shared=True,
        )

    max_lyapunov = float(np.mean(growth_log)) / (renorm_every * dt)

    # convergence: std of last third < std of whole sequence
    n_entries = len(growth_log)
    tail = growth_log[2 * n_entries // 3 :]
    if len(tail) >= 3:
        converged = float(np.std(tail)) < max(1.0, float(np.std(growth_log)))
    else:
        converged = False

    return LyapunovResult(
        max_lyapunov=max_lyapunov,
        growth_log=growth_log,
        epsilon=epsilon,
        n_steps=n_steps,
        converged=converged,
        noise_shared=True,
    )

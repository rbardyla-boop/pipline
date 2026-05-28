"""
topology — Localized interaction geometry for NonEquilibriumSandbox (Part XIII).

Kernel protocol: any callable f(dist: np.ndarray) -> np.ndarray where dist is
an (N, N) array of pairwise distances.  Built-in kernels are frozen dataclasses.

LocalizedSandbox wraps NonEquilibriumSandbox and replaces the all-to-all
coupling K_ij with K_ij * phi(|x_i - x_j|).  The original redistribute_mass
(env_mass channel) is kept intact — Part XII proved it is load-bearing for chaos.

With kernel=AllToAllKernel() and the same seed, simulate() is bitwise-identical
to NonEquilibriumSandbox.simulate(); this is the primary correctness invariant.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import NonEquilibriumSandbox
from .lagrangian import compute_forces, compute_hamiltonian
from .observables import PhysicsTrace
from .phase_transitions import PhaseState, SurvivabilityReport, build_report

# Must match lagrangian._REPULSION_DISTANCE; duplicated to avoid importing private.
_REPULSION_DISTANCE: float = 0.8


# ---------------------------------------------------------------------------
# Locality kernels
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AllToAllKernel:
    """Identity kernel: reproduces original compute_coupling_matrix exactly."""

    name: str = "alltoall"
    xi: float = float("inf")

    def __call__(self, dist: np.ndarray) -> np.ndarray:
        return np.ones_like(dist)


@dataclass(frozen=True)
class ExponentialKernel:
    """phi(r) = exp(-r / xi).  Soft locality with characteristic length xi."""

    xi: float = 0.5
    name: str = "exponential"

    def __call__(self, dist: np.ndarray) -> np.ndarray:
        return np.exp(-dist / self.xi)


@dataclass(frozen=True)
class GaussianKernel:
    """phi(r) = exp(-r^2 / (2 * sigma^2)).  Gaussian locality envelope."""

    sigma: float = 0.3
    name: str = "gaussian"

    def __call__(self, dist: np.ndarray) -> np.ndarray:
        return np.exp(-0.5 * (dist / self.sigma) ** 2)


@dataclass(frozen=True)
class HardCutoffKernel:
    """phi(r) = 1 if r <= radius, else 0.  Strict neighborhood interaction."""

    radius: float = 0.5
    name: str = "hardcutoff"

    def __call__(self, dist: np.ndarray) -> np.ndarray:
        return (dist <= self.radius).astype(float)


# ---------------------------------------------------------------------------
# LocalizedSandbox
# ---------------------------------------------------------------------------

class LocalizedSandbox:
    """
    NonEquilibriumSandbox with a localized interaction kernel.

    The coupling matrix becomes K_ij * phi(|x_i - x_j|) instead of the
    original all-to-all K_ij = M_i * M_j / M_total.  All other physics —
    including the env_mass redistribution channel — is unchanged.
    """

    def __init__(
        self,
        *,
        n_agents: int,
        total_mass: float,
        kT_global: float,
        gamma: float,
        entropy_budget: float,
        seed: int,
        kernel=None,
        **kwargs,
    ) -> None:
        self._sb = NonEquilibriumSandbox(
            n_agents=n_agents,
            total_mass=total_mass,
            kT_global=kT_global,
            gamma=gamma,
            entropy_budget=entropy_budget,
            seed=seed,
            **kwargs,
        )
        self._kernel = kernel if kernel is not None else AllToAllKernel()

    # ------------------------------------------------------------------
    # Proxy attributes (needed by estimate_lyapunov and sample_positions)
    # ------------------------------------------------------------------

    @property
    def manifold(self):
        return self._sb.manifold

    @property
    def thermostat(self):
        return self._sb.thermostat

    @property
    def dt(self) -> float:
        return self._sb.dt

    @property
    def k_conf(self) -> float:
        return self._sb.k_conf

    @property
    def M_total(self) -> float:
        return self._sb.M_total

    @property
    def rng(self):
        return self._sb.rng

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def simulate(
        self,
        n_steps: int,
        concept_force: float = 0.5,
    ) -> SurvivabilityReport:
        """Run n_steps of the simulation with localized coupling.

        Loop is duplicated from NonEquilibriumSandbox.simulate() with the sole
        change that compute_coupling_matrix is replaced by self._coupling().
        """
        sb = self._sb
        trace = PhysicsTrace()
        phase_history: list[PhaseState] = []
        dt = sb.dt

        coupling = self._coupling(sb.manifold.mass, sb.manifold.x)

        for step in range(n_steps):
            x = sb.manifold.x
            p = sb.manifold.p
            mass = sb.manifold.mass

            F = compute_forces(x, coupling, sb.k_conf) + concept_force * np.sin(x)

            p = p + F * dt
            p = sb.thermostat.apply(p, mass, coupling, dt, sb.rng)
            x = x + p * dt

            sb.manifold.set_kinematics(x, p)
            sb.manifold.redistribute_mass()

            mass = sb.manifold.mass
            x = sb.manifold.x
            p = sb.manifold.p
            coupling = self._coupling(mass, x)

            H = compute_hamiltonian(mass, x, p, coupling, sb.k_conf)
            ep = sb.thermostat.entropy_production_rate(mass, p, coupling)

            trace.record(
                step=step,
                H=H,
                ep=ep,
                mass_var=float(np.var(mass)),
                x_m=float(x.mean()),
                env=sb.manifold.env_mass,
            )

            if step >= sb.detector.window:
                phase_history.append(sb.detector.classify(trace, sb.M_total))

        return build_report(trace, phase_history, sb.M_total)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _coupling(self, mass: np.ndarray, x: np.ndarray) -> np.ndarray:
        """Localized coupling: K_ij * phi(|x_i - x_j|)."""
        dist = np.abs(x[:, None] - x[None, :])
        k = np.outer(mass, mass) / self._sb.M_total
        k[dist > _REPULSION_DISTANCE] *= -0.5
        np.fill_diagonal(k, 0.0)
        return k * self._kernel(dist)


__all__ = [
    "AllToAllKernel",
    "ExponentialKernel",
    "GaussianKernel",
    "HardCutoffKernel",
    "LocalizedSandbox",
]

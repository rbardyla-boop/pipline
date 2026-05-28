"""
thermodynamic_limit — Density-preserving geometry with periodic boundary
conditions for Part XIV.

Key differences from NonEquilibriumSandbox:
  - x_range(N) = N / (2 * density): constant agent density as N grows
  - Toroidal minimum-image distances for coupling
  - Minimum-image displacements for spring force
  - Position wrapping after each drift step
  - k_conf = 0 by default: confining well breaks PBC translational symmetry

DensityPreservingSandbox exposes the same proxy attributes as LocalizedSandbox
so it can be passed to estimate_lyapunov (which uses all-to-all open-BC
coupling internally; PBC-correct Lyapunov is deferred to Part XV).
"""

from __future__ import annotations

import numpy as np

from . import NonEquilibriumSandbox
from .lagrangian import compute_kinetic
from .observables import PhysicsTrace
from .phase_transitions import PhaseState, SurvivabilityReport, build_report

_REPULSION_DISTANCE: float = 0.8   # must match lagrangian._REPULSION_DISTANCE


# ---------------------------------------------------------------------------
# Module-level helpers (exported for tests)
# ---------------------------------------------------------------------------

def _periodic_distance(x: np.ndarray, L: float) -> np.ndarray:
    """Toroidal minimum-image pairwise distances: min(|dx|, L - |dx|)."""
    diff = np.abs(x[:, None] - x[None, :])
    return np.minimum(diff, L - diff)


def _wrap_periodic(x: np.ndarray, L: float) -> np.ndarray:
    """Wrap positions into [-L/2, L/2)."""
    return ((x + L / 2.0) % L) - L / 2.0


# ---------------------------------------------------------------------------
# DensityPreservingSandbox
# ---------------------------------------------------------------------------

class DensityPreservingSandbox:
    """
    NonEquilibriumSandbox with density-preserving geometry and periodic BCs.

    x_range(N) = N / (2 * density)  →  rho = N / L = density (constant).

    Position wrapping (toroidal): x ← (x + L/2) % L - L/2 after each drift.
    Coupling distance: minimum-image  min(|dx|, L - |dx|).
    Spring force: minimum-image displacement  dx - L * round(dx / L).
    Hamiltonian: minimum-image spring term for self-consistent energy tracking.
    k_conf defaults to 0: confining well is not appropriate for PBC geometry.
    """

    def __init__(
        self,
        *,
        n_agents: int,
        density: float,
        kT_global: float,
        gamma: float,
        entropy_budget: float,
        seed: int,
        m_per_agent: float = 8.0,
        k_conf: float = 0.0,
        d: int = 1,
        **kwargs,
    ) -> None:
        if d != 1:
            raise NotImplementedError("Only d=1 is implemented")
        self._density = density
        self._L = n_agents / density         # box length L = N / rho
        x_range = self._L / 2.0
        self._sb = NonEquilibriumSandbox(
            n_agents=n_agents,
            total_mass=m_per_agent * n_agents,
            kT_global=kT_global,
            gamma=gamma,
            entropy_budget=entropy_budget,
            seed=seed,
            x_range=x_range,
            k_conf=k_conf,
            **kwargs,
        )
        self._k_conf = k_conf

    # ------------------------------------------------------------------
    # Proxy attributes (needed by estimate_lyapunov)
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
        return self._k_conf

    @property
    def M_total(self) -> float:
        return self._sb.M_total

    @property
    def rng(self):
        return self._sb.rng

    @property
    def density(self) -> float:
        return self._density

    @property
    def box_length(self) -> float:
        return self._L

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def simulate(
        self,
        n_steps: int,
        concept_force: float = 0.5,
    ) -> SurvivabilityReport:
        """Run n_steps with PBC and density-preserving geometry."""
        report, _ = self.simulate_full(n_steps, concept_force)
        return report

    def simulate_full(
        self,
        n_steps: int,
        concept_force: float = 0.5,
    ) -> tuple[SurvivabilityReport, PhysicsTrace]:
        """Run n_steps and return (SurvivabilityReport, PhysicsTrace).

        The trace is used by density_scan.py to compute Binder U_4 and chi
        without a separate perturbation run.
        """
        sb = self._sb
        L = self._L
        trace = PhysicsTrace()
        phase_history: list[PhaseState] = []
        dt = sb.dt

        coupling = self._coupling(sb.manifold.mass, sb.manifold.x)

        for step in range(n_steps):
            x = sb.manifold.x
            p = sb.manifold.p
            mass = sb.manifold.mass

            F = self._forces(x, coupling) + concept_force * np.sin(x)

            p = p + F * dt
            p = sb.thermostat.apply(p, mass, coupling, dt, sb.rng)
            x = _wrap_periodic(x + p * dt, L)   # drift + periodic wrap

            sb.manifold.set_kinematics(x, p)
            sb.manifold.redistribute_mass()

            mass = sb.manifold.mass
            x = sb.manifold.x
            p = sb.manifold.p
            coupling = self._coupling(mass, x)

            H = self._hamiltonian(mass, x, p, coupling)
            ep = sb.thermostat.entropy_production_rate(mass, p, coupling)

            trace.record(
                step=step,
                H=H,
                ep=ep,
                mass_var=float(np.var(mass)),
                x_m=float(x.mean()),
                env=sb.manifold.env_mass,
            )
            trace.record_phi(
                float(mass[x >= 0.0].sum() - mass[x < 0.0].sum()) / self.M_total
            )

            if step >= sb.detector.window:
                phase_history.append(sb.detector.classify(trace, sb.M_total))

        return build_report(trace, phase_history, sb.M_total), trace

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _coupling(self, mass: np.ndarray, x: np.ndarray) -> np.ndarray:
        """All-to-all K_ij using minimum-image distances."""
        dist = _periodic_distance(x, self._L)
        k = np.outer(mass, mass) / self._sb.M_total
        k[dist > _REPULSION_DISTANCE] *= -0.5
        np.fill_diagonal(k, 0.0)
        return k

    def _forces(self, x: np.ndarray, coupling: np.ndarray) -> np.ndarray:
        """Spring force with minimum-image displacements + optional confining."""
        dx_raw = x[:, None] - x[None, :]
        dx = dx_raw - self._L * np.round(dx_raw / self._L)
        spring = -(coupling * dx).sum(axis=1)
        return spring + (-self._k_conf * x)

    def _hamiltonian(
        self,
        mass: np.ndarray,
        x: np.ndarray,
        p: np.ndarray,
        coupling: np.ndarray,
    ) -> float:
        """Hamiltonian using minimum-image displacements for self-consistency."""
        dx_raw = x[:, None] - x[None, :]
        dx = dx_raw - self._L * np.round(dx_raw / self._L)
        V_spring = 0.5 * float((coupling * dx ** 2).sum())
        V_conf = 0.5 * self._k_conf * float((x ** 2).sum())
        return float(compute_kinetic(mass, p)) + V_spring + V_conf


__all__ = [
    "DensityPreservingSandbox",
    "_periodic_distance",
    "_wrap_periodic",
]

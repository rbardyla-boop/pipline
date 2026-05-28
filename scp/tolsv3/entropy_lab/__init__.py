"""
entropy_lab — Non-Equilibrium Entropy Budget Engine (Part X)

A standalone scientific instrument for studying attention-mass dynamics
under constrained stochastic pressure. Isolated from SCP Rust runtime
and TOLS pattern-recall core to preserve falsifiability.

Key classes:
  NonEquilibriumSandbox  — configure and run a simulation
  SurvivabilityReport    — frozen result with 7 falsifiable observables
  PhaseState             — NESS / METASTABLE / FROZEN / RUNAWAY / DIFFUSIVE

Quick start:
  from entropy_lab import NonEquilibriumSandbox
  sb = NonEquilibriumSandbox(n_agents=50, total_mass=500.0, kT_global=0.5,
                             gamma=0.1, entropy_budget=10.0, seed=0)
  report = sb.simulate(n_steps=400, concept_force=0.5)
  print(report)
"""

from __future__ import annotations

import numpy as np

from .dissipation import LangevinThermostat
from .lagrangian import (
    compute_coupling_matrix,
    compute_forces,
    compute_hamiltonian,
    compute_kinetic,
    compute_potential,
)
from .manifold import AttentionManifold
from .observables import PhysicsTrace
from .phase_transitions import (
    NESSDetector,
    PhaseState,
    SurvivabilityReport,
    build_report,
)


class NonEquilibriumSandbox:
    """
    Non-equilibrium attention-mass simulator.

    Physics summary:
      - N agents carry mass M_i; Σ M_i + M_env = M_total (strictly conserved)
      - Positions x_i and momenta p_i evolve via symplectic-Euler + Langevin
      - Coupling k_ij = M_i·M_j / M_total, with sign flip at distance > 0.8
      - Local temperature kT_i varies by neighborhood coordination strength
      - Soft entropy budget: gamma_eff = gamma_0 / (1 + alpha * Sigma_dot / budget)
      - External concept forcing: F_concept_i = concept_force * sin(x_i)

    Integration scheme (one force computation per step):
      1. Compute coupling K and forces F(x_t)
      2. Kick: p += (F + F_concept) * dt
      3. Langevin O-step: p <- dissipate(p) + noise(p)
      4. Drift: x += p * dt
      5. Redistribute mass (velocity-weighted)
      6. Record observables; K cached for next step
    """

    def __init__(
        self,
        n_agents: int = 100,
        total_mass: float = 1000.0,
        kT_global: float = 0.5,
        gamma: float = 0.1,
        entropy_budget: float = 10.0,
        beta: float = 1.0,
        alpha: float = 2.0,
        k_conf: float = 2.0,
        dt: float = 0.05,
        ness_window: int = 50,
        seed: int | None = None,
        x_range: float = 1.0,
    ) -> None:
        self.rng = np.random.default_rng(seed)
        self.manifold = AttentionManifold(n_agents, total_mass, self.rng, x_range=x_range)
        self.thermostat = LangevinThermostat(gamma, kT_global, entropy_budget, beta, alpha)
        self.detector = NESSDetector(window=ness_window)
        self.dt = dt
        self.k_conf = k_conf
        self.M_total = total_mass

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def simulate(
        self,
        n_steps: int,
        concept_force: float = 0.5,
    ) -> SurvivabilityReport:
        """Run n_steps of the non-equilibrium simulation from the current state.

        concept_force: amplitude of the sinusoidal external perturbation,
        analogous to a "concept" entering the attention field.
        Multiple calls continue from where the previous run ended.
        """
        trace = PhysicsTrace()
        phase_history: list[PhaseState] = []
        dt = self.dt

        # Pre-compute coupling at current state (cached between steps)
        coupling = compute_coupling_matrix(
            self.manifold.mass, self.manifold.x, self.M_total
        )

        for step in range(n_steps):
            x = self.manifold.x
            p = self.manifold.p
            mass = self.manifold.mass

            # Conservative force (spring + confining well) + concept perturbation
            F = compute_forces(x, coupling, self.k_conf) + concept_force * np.sin(x)

            # Kick
            p = p + F * dt

            # Langevin O-step (dissipation + noise)
            p = self.thermostat.apply(p, mass, coupling, dt, self.rng)

            # Drift
            x = x + p * dt

            # Commit kinematics, then redistribute mass
            self.manifold.set_kinematics(x, p)
            self.manifold.redistribute_mass()

            # Recompute coupling at new state (used for observables + next step)
            mass = self.manifold.mass
            x = self.manifold.x
            p = self.manifold.p
            coupling = compute_coupling_matrix(mass, x, self.M_total)

            H = compute_hamiltonian(mass, x, p, coupling, self.k_conf)
            ep = self.thermostat.entropy_production_rate(mass, p, coupling)

            trace.record(
                step=step,
                H=H,
                ep=ep,
                mass_var=float(np.var(mass)),
                x_m=float(x.mean()),
                env=self.manifold.env_mass,
            )

            if step >= self.detector.window:
                phase_history.append(self.detector.classify(trace, self.M_total))

        return build_report(trace, phase_history, self.M_total)


__all__ = [
    "NonEquilibriumSandbox",
    "SurvivabilityReport",
    "PhaseState",
    "PhysicsTrace",
]

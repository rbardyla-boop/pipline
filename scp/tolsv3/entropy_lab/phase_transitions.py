from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

import numpy as np

from .observables import (
    PhysicsTrace,
    measure_autocorr_drift,
    measure_autocorrelation_decay_time,
    measure_coordination_cost,
    measure_entropy_production_rate,
    measure_synchronization_pressure,
)


class PhaseState(Enum):
    NESS = auto()        # Non-equilibrium steady state: the target regime
    METASTABLE = auto()  # Energy-stable but coherence time is shrinking (τ_corr drifting)
    FROZEN = auto()      # Dissipation won — entropy production collapsed
    RUNAWAY = auto()     # Injection won — Hamiltonian growing without bound
    DIFFUSIVE = auto()   # Mass dissolved into environment — structure lost


@dataclass(frozen=True)
class SurvivabilityReport:
    """All falsifiable observables from a completed simulation run."""

    phase_state: PhaseState
    survivability: float               # fraction of classified steps in NESS
    entropy_production_rate: float     # mean Sigma_dot over full trace
    synchronization_pressure: float    # Var(x) / E[x²]
    coordination_cost: float           # H_late / H_early
    autocorrelation_decay_time: float  # τ_corr in steps
    autocorr_drift: float              # OLS slope of τ_corr across trace windows
    mass_variance_final: float         # Var(M_i) near end of trace
    env_mass_fraction: float           # M_env / M_total at last recorded step

    def __str__(self) -> str:
        return (
            f"PhaseState: {self.phase_state.name}\n"
            f"  survivability         = {self.survivability:.3f}\n"
            f"  entropy_production    = {self.entropy_production_rate:.4e}\n"
            f"  sync_pressure         = {self.synchronization_pressure:.4f}\n"
            f"  coordination_cost     = {self.coordination_cost:.4f}\n"
            f"  tau_corr              = {self.autocorrelation_decay_time:.2f} steps\n"
            f"  tau_corr_drift        = {self.autocorr_drift:.4f}\n"
            f"  mass_variance_final   = {self.mass_variance_final:.4e}\n"
            f"  env_mass_fraction     = {self.env_mass_fraction:.3f}"
        )


class NESSDetector:
    """
    Classifies the phase state from a sliding window over a PhysicsTrace.

    True NESS requires all four conditions simultaneously:
      1. |delta_H| < eps_energy       — mean energy is stable
      2. mean(Sigma_dot) > eps_entropy — entropy production is active
      3. std(H) > eps_fluct            — fluctuations are present
      4. tau_corr drift >= -eps_corr   — coherence time is not shrinking

    METASTABLE: conditions 1-3 met, but coherence time τ_corr is drifting
    downward across successive windows — will eventually collapse.

    The metastability check requires at least 2 * window steps to have
    enough sub-windows for a meaningful drift estimate.
    """

    def __init__(
        self,
        window: int = 50,
        eps_energy: float = 5.0,
        eps_entropy: float = 1e-4,
        eps_fluct: float = 1e-3,
        eps_corr_drift: float = 0.1,
    ) -> None:
        self.window = window
        self.eps_energy = eps_energy
        self.eps_entropy = eps_entropy
        self.eps_fluct = eps_fluct
        self.eps_corr_drift = eps_corr_drift

    def classify(self, trace: PhysicsTrace, M_total: float) -> PhaseState:
        n = len(trace)
        if n < self.window:
            return PhaseState.FROZEN

        H = np.array(trace.hamiltonian[-self.window:])
        ep = np.array(trace.entropy_rate[-self.window:])
        env = np.array(trace.env_mass[-self.window:])
        mv = np.array(trace.mass_variance[-self.window:])

        mean_ep = float(ep.mean())
        sigma_H = float(H.std())
        half = max(1, len(H) // 2)
        delta_H = abs(float(H[half:].mean()) - float(H[:half].mean()))
        mean_env_frac = float(env.mean()) / M_total

        # RUNAWAY: H increasing substantially in the window.
        # Compare averaged first/last fifths to avoid endpoint noise.
        # Do NOT use H[-1] > H[0] * 1.5 — that misfires when H[0] < 0.
        fifth = max(1, len(H) // 5)
        H_early = float(H[:fifth].mean())
        H_late = float(H[-fifth:].mean())
        H_increase = H_late - H_early
        H_scale = max(abs(H_early), 1e-9)
        if H_increase > H_scale * 0.5 and H_increase > self.eps_energy * 10:
            return PhaseState.RUNAWAY

        # DIFFUSIVE: mass has dissolved into environment
        if mean_env_frac > 0.6 and float(mv.mean()) < 1e-3:
            return PhaseState.DIFFUSIVE

        # FROZEN: entropy production has stopped
        if mean_ep < self.eps_entropy:
            return PhaseState.FROZEN

        energy_stable = delta_H < self.eps_energy
        fluctuating = sigma_H > self.eps_fluct

        if not (energy_stable and fluctuating):
            return PhaseState.FROZEN

        # Discriminate NESS from METASTABLE: is coherence time shrinking?
        drift = measure_autocorr_drift(trace, n_windows=4)
        if drift < -self.eps_corr_drift:
            return PhaseState.METASTABLE

        return PhaseState.NESS


def build_report(
    trace: PhysicsTrace,
    phase_history: list[PhaseState],
    M_total: float,
) -> SurvivabilityReport:
    ness_steps = sum(1 for p in phase_history if p == PhaseState.NESS)
    survivability = ness_steps / max(len(phase_history), 1)

    final_phase = phase_history[-1] if phase_history else PhaseState.FROZEN

    mv_tail = trace.mass_variance[-10:] if len(trace.mass_variance) >= 10 else trace.mass_variance
    env_last = trace.env_mass[-1] if trace.env_mass else 0.0

    return SurvivabilityReport(
        phase_state=final_phase,
        survivability=survivability,
        entropy_production_rate=measure_entropy_production_rate(trace),
        synchronization_pressure=measure_synchronization_pressure(trace),
        coordination_cost=measure_coordination_cost(trace),
        autocorrelation_decay_time=measure_autocorrelation_decay_time(trace),
        autocorr_drift=measure_autocorr_drift(trace),
        mass_variance_final=float(np.var(mv_tail)) if mv_tail else 0.0,
        env_mass_fraction=float(env_last) / M_total,
    )

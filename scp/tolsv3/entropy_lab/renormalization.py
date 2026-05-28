"""
renormalization — Intensive mass redistribution replacing the absolute-threshold
channel that causes ep/N to be non-intensive across system sizes.

Root cause of non-intensivity in the original:
  total_bleed = 0.02 * N_slow * M_avg = 0.02 * N * P(slow) * M_avg
  P(slow) grows with N because fixed x_range + more agents → denser coupling →
  lower kT_i → more agents below the |p|<0.1 threshold.

Fix: gradient-normalized soft weights with an intensive budget.
  total_transfer = m_avg * bleed_rate  (constant per N by construction)
  bleed_weights_i ∝ 1/(|p_i| + eps)   — slow agents bleed more
  absorb_weights_i ∝ |p_i|             — fast agents absorb more
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from entropy_lab import NonEquilibriumSandbox, SurvivabilityReport


@dataclass(frozen=True)
class IntensiveRedistributor:
    """Gradient-normalized mass redistribution with an intensive transfer budget."""

    bleed_rate: float = 0.02
    eps: float = 1e-6

    def redistribute(
        self,
        mass: np.ndarray,
        p: np.ndarray,
        m_avg: float,
    ) -> np.ndarray:
        """Return new mass array conserving total agent mass.

        total_transfer = m_avg * bleed_rate is independent of N.
        delta sums to zero (absorb and bleed weights each normalize to 1),
        so mass.sum() is preserved before the clip step.
        After clipping negatives the sum is restored by rescaling.
        """
        abs_p = np.abs(p)

        bleed_w = 1.0 / (abs_p + self.eps)
        bleed_w = bleed_w / bleed_w.sum()

        absorb_sum = abs_p.sum()
        if absorb_sum < self.eps:
            absorb_w = np.ones(len(p)) / len(p)
        else:
            absorb_w = abs_p / absorb_sum

        total_transfer = m_avg * self.bleed_rate
        delta = (absorb_w - bleed_w) * total_transfer
        new_mass = mass + delta

        new_mass = np.maximum(new_mass, 0.0)
        total = new_mass.sum()
        if total > 0.0:
            new_mass = new_mass * (mass.sum() / total)
        return new_mass


class RenormalizedSandbox:
    """NonEquilibriumSandbox with intensive mass redistribution.

    Only the redistribution step differs from NonEquilibriumSandbox.
    All Langevin dynamics, coupling, thermostat, and observables are unchanged.
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
        bleed_rate: float = 0.02,
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
        self._redistributor = IntensiveRedistributor(bleed_rate=bleed_rate)
        self._m_avg: float = total_mass / n_agents

    # ------------------------------------------------------------------
    # Proxy attributes for code that inspects sandbox internals
    # (e.g. estimate_lyapunov, sample_positions from correlations.py)
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
    # Public interface
    # ------------------------------------------------------------------

    def simulate(
        self,
        n_steps: int,
        concept_force: float = 0.5,
    ) -> SurvivabilityReport:
        """Run n_steps with intensive redistribution.

        Patches manifold.redistribute_mass for the duration of the call.
        The original method is always restored in the finally block, even on error.

        Python method resolution checks instance __dict__ before the class,
        so assigning to manifold.redistribute_mass creates an instance attribute
        that shadows the bound class method without any special binding.
        """
        manifold = self._sb.manifold
        redistributor = self._redistributor
        m_avg = self._m_avg

        def _intensive_redistribute():
            new_mass = redistributor.redistribute(manifold._mass, manifold._p, m_avg)
            manifold._mass[:] = new_mass
            manifold.project_mass()

        manifold.redistribute_mass = _intensive_redistribute
        try:
            return self._sb.simulate(n_steps=n_steps, concept_force=concept_force)
        finally:
            del manifold.redistribute_mass

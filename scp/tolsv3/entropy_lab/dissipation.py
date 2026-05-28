from __future__ import annotations

import numpy as np


class LangevinThermostat:
    """
    Langevin thermostat with two Part-X upgrades over a canonical bath:

    1. Local temperature field
       kT_i = kT_global / (1 + beta * coordination_i)
       Agents in tight clusters get lower noise (protected); boundary agents
       get higher stochastic forcing (more vulnerable). Prevents the globally-
       homogeneous bath from erasing emergent structure under high-kT regimes.

    2. Soft entropy budget
       gamma_eff = gamma_0 / (1 + alpha * Sigma_dot / budget)
       As entropy production approaches the budget, effective dissipation
       continuously decreases — no hard clipping, no artificial phase boundaries.
       This produces real critical slowing and smooth bifurcations.
    """

    def __init__(
        self,
        gamma: float,
        kT_global: float,
        entropy_budget: float,
        beta: float = 1.0,
        alpha: float = 2.0,
    ) -> None:
        self.gamma = gamma
        self.kT_global = kT_global
        self.entropy_budget = entropy_budget
        self.beta = beta
        self.alpha = alpha

    # ------------------------------------------------------------------
    # Core thermodynamic quantities
    # ------------------------------------------------------------------

    def local_temperature(self, coupling: np.ndarray) -> np.ndarray:
        """kT_i = kT_global / (1 + beta * Σ_j |k_ij|)"""
        coordination = np.abs(coupling).sum(axis=1)
        return self.kT_global / (1.0 + self.beta * coordination)

    def effective_gamma(self, ep_rate: float) -> float:
        """gamma_eff = gamma_0 / (1 + alpha * Sigma_dot / budget)

        Smooth, monotone-decreasing function of entropy production rate.
        Never clips; always positive.
        """
        return self.gamma / (1.0 + self.alpha * max(ep_rate, 0.0) / self.entropy_budget)

    def entropy_production_rate(
        self,
        mass: np.ndarray,
        p: np.ndarray,
        coupling: np.ndarray,
    ) -> float:
        """Sigma_dot = Σ_i (gamma / kT_i) * M_i * p_i²

        Always >= 0 (2nd-law grounded). Uses base gamma (not gamma_eff) to
        avoid circular dependence: gamma_eff depends on this quantity.
        """
        kT_i = self.local_temperature(coupling)
        return float((self.gamma / kT_i * mass * p ** 2).sum())

    # ------------------------------------------------------------------
    # Ornstein-Uhlenbeck O-step
    # ------------------------------------------------------------------

    def apply(
        self,
        p: np.ndarray,
        mass: np.ndarray,
        coupling: np.ndarray,
        dt: float,
        rng: np.random.Generator,
    ) -> np.ndarray:
        """Apply dissipation + noise to momenta (the Langevin O-step).

        Returns updated momenta. x and mass are unchanged.

        Fluctuation-dissipation is satisfied per-agent:
          sigma_i = sqrt(2 * gamma_eff * kT_i * dt)
        so detailed balance holds at each local temperature.
        """
        kT_i = self.local_temperature(coupling)
        ep_rate = self.entropy_production_rate(mass, p, coupling)
        g_eff = self.effective_gamma(ep_rate)

        dissipated = p * (1.0 - g_eff * dt)
        sigma = np.sqrt(np.maximum(2.0 * g_eff * kT_i * dt, 0.0))
        noise = rng.standard_normal(len(p)) * sigma

        return dissipated + noise

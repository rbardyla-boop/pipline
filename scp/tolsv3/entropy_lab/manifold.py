from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class AgentState:
    x: float
    p: float
    mass: float


class AttentionManifold:
    """
    N agents with conserved total attention mass: Σ M_i + M_env = M_total.

    Positions (x) and momenta (p) evolve under external dynamics.
    Mass redistributes each step based on agent velocity — fast agents
    absorb from the environment, slow agents bleed mass back.
    """

    def __init__(
        self,
        n_agents: int,
        total_mass: float,
        rng: np.random.Generator,
        x_range: float = 1.0,
    ) -> None:
        self.n = n_agents
        self.M_total = total_mass

        self._x: np.ndarray = rng.uniform(-x_range, x_range, n_agents)
        self._p: np.ndarray = np.zeros(n_agents)
        # 80% of mass to agents, 20% to environment
        self._mass: np.ndarray = np.full(n_agents, total_mass * 0.8 / n_agents)
        self._env_mass: float = total_mass * 0.2

    # ------------------------------------------------------------------
    # Read-only state access
    # ------------------------------------------------------------------

    @property
    def x(self) -> np.ndarray:
        return self._x.copy()

    @property
    def p(self) -> np.ndarray:
        return self._p.copy()

    @property
    def mass(self) -> np.ndarray:
        return self._mass.copy()

    @property
    def env_mass(self) -> float:
        return self._env_mass

    # ------------------------------------------------------------------
    # State mutation (called only by the integrator)
    # ------------------------------------------------------------------

    def set_kinematics(self, x: np.ndarray, p: np.ndarray) -> None:
        self._x = x.copy()
        self._p = p.copy()

    def redistribute_mass(
        self,
        speed_scale: float = 0.05,
        decay_scale: float = 0.02,
    ) -> None:
        """
        Attention mass flows toward high-velocity agents (absorption from env)
        and away from sluggish agents (bleed back to env).
        """
        speeds = np.abs(self._p)

        fast = speeds > 1.0
        if fast.any() and self._env_mass > 0.1:
            n_fast = int(fast.sum())
            per_agent = min(self._env_mass * speed_scale / n_fast, 0.5)
            self._mass[fast] += per_agent
            self._env_mass -= per_agent * n_fast

        slow = speeds < 0.1
        if slow.any():
            bleed = self._mass[slow] * decay_scale
            self._mass[slow] -= bleed
            self._env_mass += float(bleed.sum())

        self.project_mass()

    def project_mass(self) -> None:
        """Enforce Σ M_i + M_env = M_total (corrects floating-point drift)."""
        self._mass = np.maximum(self._mass, 0.0)
        self._env_mass = max(0.0, self._env_mass)
        drift = self.M_total - (self._mass.sum() + self._env_mass)
        if abs(drift) > 1e-9:
            correction = drift / (self.n + 1)
            self._mass += correction
            self._env_mass += correction

    def snapshot(self) -> list[AgentState]:
        return [
            AgentState(x=float(self._x[i]), p=float(self._p[i]), mass=float(self._mass[i]))
            for i in range(self.n)
        ]

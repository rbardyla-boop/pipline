"""
density_scan — Primary scientific experiment for Part XIV.

Sweeps N at fixed agent density rho = N / L, using DensityPreservingSandbox
with periodic boundary conditions. Tests whether ep/N is intensive when the
thermodynamic limit is taken correctly (L ∝ N, rho fixed).

Default density=16.67 agents/unit length matches the Part XI baseline:
  N=10 -> x_range=0.30  (same as scaling_scan.py)
  N=20 -> x_range=0.60
  N=50 -> x_range=1.50
  N=100 -> x_range=3.00

Also measures Binder cumulant U_4 and susceptibility chi = N*Var(x_mean)
from the PhysicsTrace — the FSS infrastructure for Part XV.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from entropy_lab.scaling_observables import binder_cumulant, susceptibility_from_trace
from entropy_lab.thermodynamic_limit import DensityPreservingSandbox


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DensityPoint:
    n_agents: int
    density: float
    box_length: float
    ep_per_agent: float
    binder_u4: float
    chi_fluct: float     # N * Var(x_mean)
    phase: str
    error: str | None


@dataclass(frozen=True)
class DensityScan:
    n_values: list[int]
    density: float
    points: list[DensityPoint]
    kT: float
    gamma: float
    n_steps: int

    def ascii_table(self) -> str:
        lines = [
            f"{'N':>5}  {'L':>6}  {'ep/N':>8}  {'U_4':>7}  {'chi':>10}  phase",
            "-" * 54,
        ]
        for pt in sorted(self.points, key=lambda p: p.n_agents):
            if pt.error:
                lines.append(
                    f"{pt.n_agents:>5}  {pt.box_length:>6.3f}  "
                    f"{'ERROR':>8}  {'---':>7}  {'---':>10}  {pt.error[:20]}"
                )
            else:
                lines.append(
                    f"{pt.n_agents:>5}  {pt.box_length:>6.3f}  "
                    f"{pt.ep_per_agent:>8.4f}  {pt.binder_u4:>7.4f}  "
                    f"{pt.chi_fluct:>10.4f}  {pt.phase}"
                )
        ep_vals = [
            p.ep_per_agent for p in self.points
            if p.error is None and math.isfinite(p.ep_per_agent)
        ]
        if len(ep_vals) >= 2:
            mean_ep = float(np.mean(ep_vals))
            spread = (max(ep_vals) - min(ep_vals)) / max(abs(mean_ep), 1e-12)
            lines.append(f"\n  -> is_intensive(0.15): {self.is_intensive()}  "
                         f"(spread {spread:.1%})")
        return "\n".join(lines)

    def is_intensive(self, rel_tol: float = 0.15) -> bool:
        """True if ep/N spread across N is within rel_tol of the mean."""
        valid = [
            p.ep_per_agent for p in self.points
            if p.error is None and math.isfinite(p.ep_per_agent)
        ]
        if len(valid) < 2:
            return False
        mean_ep = float(np.mean(valid))
        if mean_ep == 0.0:
            return True
        spread = (max(valid) - min(valid)) / abs(mean_ep)
        return spread <= rel_tol


# ---------------------------------------------------------------------------
# Main sweep
# ---------------------------------------------------------------------------

def scan_density(
    n_values: tuple[int, ...] = (10, 20, 50, 100),
    *,
    density: float = 16.67,
    kT: float = 0.5,
    gamma: float = 0.1,
    m_per_agent: float = 8.0,
    budget_per_agent: float = 2.0,
    n_steps: int = 400,
    concept_force: float = 0.5,
    seed: int = 0,
    ness_window: int = 20,
    k_conf: float = 2.0,
) -> DensityScan:
    """Sweep N at fixed density with PBC; measure ep/N, Binder U_4, chi.

    All per-agent intensive parameters (m_per_agent, budget_per_agent) are
    held fixed; total_mass and entropy_budget scale proportionally with N.
    """
    points: list[DensityPoint] = []

    for n in n_values:
        params: dict = dict(
            n_agents=n,
            density=density,
            kT_global=kT,
            gamma=gamma,
            entropy_budget=float(budget_per_agent * n),
            seed=seed,
            m_per_agent=m_per_agent,
            ness_window=ness_window,
            k_conf=k_conf,
        )
        try:
            with np.errstate(over="raise", invalid="raise"):
                sb = DensityPreservingSandbox(**params)
                report, trace = sb.simulate_full(n_steps, concept_force)
                ep_per_agent = report.entropy_production_rate / n
                phase = report.phase_state.name
                u4 = binder_cumulant(trace).u4
                chi = susceptibility_from_trace(trace, n_agents=n)

            points.append(DensityPoint(
                n_agents=n,
                density=density,
                box_length=sb.box_length,
                ep_per_agent=ep_per_agent,
                binder_u4=u4,
                chi_fluct=chi,
                phase=phase,
                error=None,
            ))
        except Exception as exc:
            points.append(DensityPoint(
                n_agents=n,
                density=density,
                box_length=n / density,
                ep_per_agent=float("nan"),
                binder_u4=float("nan"),
                chi_fluct=float("nan"),
                phase="ERROR",
                error=str(exc)[:80],
            ))

    return DensityScan(
        n_values=list(n_values),
        density=density,
        points=points,
        kT=kT,
        gamma=gamma,
        n_steps=n_steps,
    )

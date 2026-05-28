"""
scaling_scan — N-scaling experiment: tests whether ep/N is intensive.

Design notes:
  - Intensive parameters held constant: kT, gamma, dt, k_conf, beta, alpha,
    m_per_agent, budget_per_agent.
  - Extensive quantities scale ∝ N: total_mass = m_per_agent * N,
    entropy_budget = budget_per_agent * N.
  - ep_per_agent = entropy_rate / n_agents measures intensivity.
  - is_intensive(rel_tol) checks spread(ep/N) / mean(ep/N) ≤ rel_tol.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from entropy_lab import NonEquilibriumSandbox


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ScalingPoint:
    n_agents: int
    ep_per_agent: float      # entropy_rate / n_agents
    env_frac: float
    phase: str
    survivability: float
    error: str | None


@dataclass(frozen=True)
class ScalingResult:
    points: list[ScalingPoint]
    m_per_agent: float
    budget_per_agent: float
    kT: float
    gamma: float
    n_steps: int
    concept_force: float

    def ascii_table(self) -> str:
        header = f"{'N':>6}  {'ep/N':>10}  {'env_frac':>9}  {'phase':<12}  {'surv':>5}"
        sep = "-" * len(header)
        rows = [header, sep]
        for p in self.points:
            if p.error:
                rows.append(f"{p.n_agents:>6}  {'ERROR':>10}  {'---':>9}  {p.error[:12]:<12}  {'---':>5}")
            else:
                rows.append(
                    f"{p.n_agents:>6}  {p.ep_per_agent:>10.4f}  "
                    f"{p.env_frac:>9.3f}  {p.phase:<12}  {p.survivability:>5.3f}"
                )
        return "\n".join(rows)

    def is_intensive(self, rel_tol: float = 0.15) -> bool:
        """True when ep/N spread across N-values is within rel_tol of the mean."""
        valid = [
            p.ep_per_agent
            for p in self.points
            if p.error is None and np.isfinite(p.ep_per_agent)
        ]
        if len(valid) < 2:
            return True
        mean_ep = sum(valid) / len(valid)
        if mean_ep == 0.0:
            return True
        spread = (max(valid) - min(valid)) / abs(mean_ep)
        return spread <= rel_tol


# ---------------------------------------------------------------------------
# Sweep
# ---------------------------------------------------------------------------

def scan_scaling(
    n_values: tuple[int, ...] = (10, 20, 50, 100, 200),
    *,
    m_per_agent: float = 8.0,
    budget_per_agent: float = 2.0,
    kT: float = 0.5,
    gamma: float = 0.1,
    n_steps: int = 400,
    concept_force: float = 0.5,
    seed: int = 0,
    record_dir: Path | None = None,
) -> ScalingResult:
    """Sweep N-values, holding intensive parameters fixed.

    M_total = m_per_agent * N and entropy_budget = budget_per_agent * N scale
    proportionally, so the per-agent thermodynamic environment is identical
    across all N.
    """
    points: list[ScalingPoint] = []

    for n in n_values:
        params = dict(
            n_agents=int(n),
            total_mass=float(m_per_agent * n),
            kT_global=kT,
            gamma=gamma,
            entropy_budget=float(budget_per_agent * n),
            seed=seed,
            x_range=0.3,
            ness_window=20,
        )
        point = _run_point(params, n_steps, concept_force, record_dir)
        points.append(point)

    return ScalingResult(
        points=points,
        m_per_agent=m_per_agent,
        budget_per_agent=budget_per_agent,
        kT=kT,
        gamma=gamma,
        n_steps=n_steps,
        concept_force=concept_force,
    )


def _run_point(
    params: dict,
    n_steps: int,
    concept_force: float,
    record_dir: Path | None,
) -> ScalingPoint:
    n = params["n_agents"]
    try:
        with np.errstate(over="raise", invalid="raise"):
            sb = NonEquilibriumSandbox(**params)
            report = sb.simulate(n_steps=n_steps, concept_force=concept_force)

        if record_dir is not None:
            _persist(params, n_steps, concept_force, record_dir)

        return ScalingPoint(
            n_agents=n,
            ep_per_agent=report.entropy_production_rate / n,
            env_frac=report.env_mass_fraction,
            phase=report.phase_state.name,
            survivability=report.survivability,
            error=None,
        )
    except Exception as exc:
        return ScalingPoint(
            n_agents=n,
            ep_per_agent=float("nan"),
            env_frac=float("nan"),
            phase="ERROR",
            survivability=0.0,
            error=repr(exc),
        )


def _persist(params, n_steps, concept_force, record_dir):
    try:
        from instrumentation.trace_store import run_and_record
        run_and_record(params, n_steps, concept_force, out_dir=Path(record_dir))
    except Exception:
        pass

"""
phase_scan — (kT, γ) phase diagram sweep.

Design notes:
  - Per-point exception isolation: each grid point is wrapped in try/except AND
    np.errstate(over="raise", invalid="raise") so silent NaN blow-ups become
    catchable ERROR entries.  The sweep never aborts.
  - Seed policy: same seed for all points by default so phase is a clean
    function of (kT, γ).
  - When record_dir is set, each successful point is persisted via run_and_record.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from entropy_lab import NonEquilibriumSandbox, PhaseState


# ASCII symbols for each phase state
_PHASE_SYMBOL: dict[str, str] = {
    "NESS": "=",
    "METASTABLE": "~",
    "FROZEN": "*",
    "RUNAWAY": "^",
    "DIFFUSIVE": ".",
    "ERROR": "X",
}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GridPoint:
    kT: float
    gamma: float
    phase: str            # PhaseState.name or "ERROR"
    survivability: float
    entropy_rate: float
    error: str | None     # repr(exception) if ERROR, else None


@dataclass(frozen=True)
class PhaseDiagram:
    kT_values: list[float]
    gamma_values: list[float]
    points: list[GridPoint]    # row-major: kT outer, gamma inner
    fixed_params: dict
    n_steps: int
    concept_force: float

    def grid(self) -> list[list[GridPoint]]:
        n_gamma = len(self.gamma_values)
        return [
            self.points[i * n_gamma : (i + 1) * n_gamma]
            for i in range(len(self.kT_values))
        ]

    def ascii_map(self) -> str:
        """Print phase map with kT rows and γ columns.

        Legend: NESS= METASTABLE~ FROZEN* RUNAWAY^ DIFFUSIVE. ERRORX
        """
        lines = []
        gamma_header = "  ".join(f"{g:.3f}" for g in self.gamma_values)
        lines.append(f"kT \\ γ  {gamma_header}")
        lines.append("-" * (8 + 7 * len(self.gamma_values)))

        for row_kT, row_pts in zip(self.kT_values, self.grid()):
            symbols = "       ".join(_PHASE_SYMBOL.get(pt.phase, "?") for pt in row_pts)
            lines.append(f"{row_kT:6.3f}  {symbols}")

        lines.append("")
        lines.append("Legend: NESS= METASTABLE~ FROZEN* RUNAWAY^ DIFFUSIVE. ERRORX")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Sweep
# ---------------------------------------------------------------------------

def scan_phase_diagram(
    kT_values: list[float],
    gamma_values: list[float],
    *,
    fixed_params: dict | None = None,
    n_steps: int = 400,
    concept_force: float = 0.5,
    record_dir: Path | None = None,
) -> PhaseDiagram:
    """Sweep (kT, γ) grid and classify each point.

    Parameters
    ----------
    kT_values, gamma_values:
        Grid axes.
    fixed_params:
        Additional NonEquilibriumSandbox kwargs (e.g. n_agents, seed, x_range).
        Defaults to n_agents=20, total_mass=200.0, seed=0, x_range=0.3.
    record_dir:
        If set, each point is persisted as a JSON ExperimentRecord.
    """
    base = dict(
        n_agents=20, total_mass=200.0, seed=0, x_range=0.3,
        entropy_budget=100.0, ness_window=20,
    )
    if fixed_params:
        base.update(fixed_params)

    points: list[GridPoint] = []

    for kT in kT_values:
        for gamma in gamma_values:
            params = dict(base, kT_global=float(kT), gamma=float(gamma))
            point = _run_point(params, n_steps, concept_force, record_dir)
            points.append(point)

    return PhaseDiagram(
        kT_values=list(kT_values),
        gamma_values=list(gamma_values),
        points=points,
        fixed_params=base,
        n_steps=n_steps,
        concept_force=concept_force,
    )


def _run_point(
    params: dict,
    n_steps: int,
    concept_force: float,
    record_dir: Path | None,
) -> GridPoint:
    kT = params["kT_global"]
    gamma = params["gamma"]
    try:
        with np.errstate(over="raise", invalid="raise"):
            sb = NonEquilibriumSandbox(**params)
            report = sb.simulate(n_steps=n_steps, concept_force=concept_force)

        if record_dir is not None:
            _persist(params, n_steps, concept_force, report, record_dir)

        return GridPoint(
            kT=kT,
            gamma=gamma,
            phase=report.phase_state.name,
            survivability=report.survivability,
            entropy_rate=report.entropy_production_rate,
            error=None,
        )
    except Exception as exc:
        return GridPoint(
            kT=kT,
            gamma=gamma,
            phase="ERROR",
            survivability=0.0,
            entropy_rate=0.0,
            error=repr(exc),
        )


def _persist(params, n_steps, concept_force, report, record_dir):
    try:
        from instrumentation.trace_store import run_and_record
        run_and_record(params, n_steps, concept_force, out_dir=Path(record_dir))
    except Exception:
        pass

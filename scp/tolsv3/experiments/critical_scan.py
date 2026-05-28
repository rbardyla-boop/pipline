"""
critical_scan — Primary scientific experiment for Part XV.

Sweeps kT for each N at fixed density, measures Binder U_4 and susceptibility chi,
and locates T_c from the crossing of U_4 curves. Also measures chi peaks and
lambda_max at each (N, kT) point.

Default parameters:
  N in (5, 10, 15, 20) — all-attractive PBC regime at density=16.67 (L/2 < 0.8)
  kT from 0.05 to 2.5, 20 log-spaced values

Expected outputs:
  - Binder table: kT rows × N columns, crossing marked with <-- T_c
  - Chi peak summary: kT_chi_peak(N) — pseudo-critical temperature per N
  - Lambda_max at each (N, kT) — critical slowing signature near T_c
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from entropy_lab.critical_scaling import (
    BinderSweep,
    CrossingEstimate,
    binder_sweep,
    collapse_data,
    find_crossing,
    susceptibility_peak,
)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CriticalScan:
    sweeps: list[BinderSweep]
    crossing: CrossingEstimate | None
    chi_peaks: list[tuple[int, float, float]]  # (n_agents, kT_peak, chi_max) per N
    density: float
    kT_values: list[float]
    n_steps: int

    def is_crossing_found(self) -> bool:
        return self.crossing is not None

    def ascii_table(self) -> str:
        n_values = [s.n_agents for s in self.sweeps]
        kT_arr = np.array(self.kT_values)

        # Header
        col_w = 8
        header = f"{'kT':>7}  " + "  ".join(f"N={n:>3}" for n in n_values)
        sep = "-" * len(header)
        lines = [
            "Binder U_4  (kT rows × N columns)",
            header,
            sep,
        ]

        # Crossing kT for annotation
        kT_c = self.crossing.kT_c if self.crossing else None

        for i, kT in enumerate(self.kT_values):
            row_parts = [f"{kT:7.4f}  "]
            for sweep in self.sweeps:
                pt = sweep.points[i]
                if pt.error is not None:
                    row_parts.append(f"{'ERR':>7}")
                else:
                    row_parts.append(f"{pt.u4:>7.4f}")
            row = "  ".join(row_parts)
            # Mark the row closest to T_c
            if kT_c is not None:
                # check if this is the closest kT to kT_c
                idx_closest = int(np.argmin(np.abs(kT_arr - kT_c)))
                if i == idx_closest:
                    row += f"  <-- T_c ≈ {kT_c:.4f}"
            lines.append(row)

        lines.append(sep)

        # Chi peak summary
        lines.append("\nSusceptibility peaks (kT where chi is maximum per N):")
        lines.append(f"  {'N':>4}  {'kT_chi_peak':>11}  {'chi_max':>9}")
        for n, kT_peak, chi_max in self.chi_peaks:
            if math.isnan(kT_peak):
                lines.append(f"  {n:>4}  {'---':>11}  {'---':>9}")
            else:
                lines.append(f"  {n:>4}  {kT_peak:>11.4f}  {chi_max:>9.4f}")

        # Lambda_max summary at each N for all kT
        lines.append("\nLambda_max (open-BC approximation):")
        lines.append(f"  {'N':>4}  " + "  ".join(f"{kT:>7.3f}" for kT in self.kT_values))
        for sweep in self.sweeps:
            lambdas = [
                f"{pt.lambda_max:>7.3f}" if pt.error is None and math.isfinite(pt.lambda_max)
                else f"{'---':>7}"
                for pt in sweep.points
            ]
            lines.append(f"  {sweep.n_agents:>4}  " + "  ".join(lambdas))

        # Crossing summary
        if self.crossing:
            c = self.crossing
            lines.append(f"\nCrossing estimate ({c.method}):")
            lines.append(f"  T_c = {c.kT_c:.4f}  [lo={c.kT_lo:.4f}, hi={c.kT_hi:.4f}]")
            lines.append(f"  U_4 at T_c = {c.u4_c:.4f}")
            lines.append(f"  Representative pair: N={c.n_crossing[0]}, N={c.n_crossing[1]}")
        else:
            lines.append("\nNo Binder crossing found in kT range.")
            lines.append("  → Adjust kT_values or density; or T_c is outside this range.")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main sweep
# ---------------------------------------------------------------------------

def scan_critical(
    n_values: tuple[int, ...] = (5, 10, 15, 20),
    kT_values: tuple[float, ...] | None = None,
    *,
    density: float = 16.67,
    gamma: float = 0.1,
    m_per_agent: float = 8.0,
    budget_per_agent: float = 2.0,
    n_steps: int = 600,
    concept_force: float = 0.3,
    seed: int = 0,
    k_conf: float = 0.0,
    ness_window: int = 30,
    lyapunov_steps: int = 150,
) -> CriticalScan:
    """Sweep kT for each N at fixed density; find Binder crossing T_c.

    Parameters
    ----------
    n_values:
        System sizes. Default (5, 10, 15, 20) stays in the all-attractive PBC
        regime at density=16.67 (L/2 < 0.8 for all N).
    kT_values:
        kT sweep values. Default: 20 log-spaced values from 0.05 to 2.5.
    density:
        Agent density ρ = N/L. Fixed across all N values.
    n_steps:
        Simulation steps per (N, kT) point. Uses tail_fraction=0.5,
        so n_steps/2 steps contribute to observables.
    lyapunov_steps:
        Steps for Benettin Lyapunov estimate at each (N, kT) point.
        Uses open-BC coupling approximation (exact for N≤20, density=16.67).
    """
    if kT_values is None:
        kT_values = tuple(np.geomspace(0.05, 2.5, 20).tolist())

    sweeps: list[BinderSweep] = []
    for n in n_values:
        sweeps.append(
            binder_sweep(
                n,
                kT_values,
                density=density,
                gamma=gamma,
                m_per_agent=m_per_agent,
                budget_per_agent=budget_per_agent,
                n_steps=n_steps,
                concept_force=concept_force,
                seed=seed,
                k_conf=k_conf,
                ness_window=ness_window,
                lyapunov_steps=lyapunov_steps,
            )
        )

    crossing = find_crossing(sweeps)
    chi_peaks = [
        (sweep.n_agents, *susceptibility_peak(sweep))
        for sweep in sweeps
    ]

    return CriticalScan(
        sweeps=sweeps,
        crossing=crossing,
        chi_peaks=chi_peaks,
        density=density,
        kT_values=list(kT_values),
        n_steps=n_steps,
    )

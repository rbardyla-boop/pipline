"""
phi_scan — Primary scientific experiment for Part XVI.

Sweeps kT for each N using:
  1. phi Binder sweep: U_4(phi) where phi = (M_right - M_left) / M_total.
     phi has genuine Z_2 symmetry, enabling a Binder crossing to locate T_c.
  2. Lyapunov sweep: lambda_max vs kT, extended to [0.05, 10.0] to capture
     the chaos-to-stable transition where lambda_max = 0.

Expected outputs:
  - phi Binder table: kT rows x N columns, crossing marked with <-- T_c
  - Lambda_max table: kT rows x N columns, chaos boundary per N
  - Chi_phi peaks: kT_chi_peak(N) per N
  - Chaos boundaries: kT where lambda_max = 0 per N
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from entropy_lab.critical_scaling import (
    BinderSweep,
    CrossingEstimate,
    LyapunovSweep,
    find_crossing,
    lyapunov_sweep,
    phi_binder_sweep,
    susceptibility_peak,
)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PhiScan:
    phi_sweeps: list[BinderSweep]
    lya_sweeps: list[LyapunovSweep]
    phi_crossing: CrossingEstimate | None
    chi_phi_peaks: list[tuple[int, float, float]]   # (N, kT_peak, chi_peak)
    chaos_boundaries: list[tuple[int, float | None]] # (N, kT_chaos) per N
    density: float
    kT_values: list[float]
    n_steps: int

    def is_phi_crossing_found(self) -> bool:
        return self.phi_crossing is not None

    def ascii_table(self) -> str:
        n_values = [s.n_agents for s in self.phi_sweeps]
        kT_arr = np.array(self.kT_values)
        kT_c = self.phi_crossing.kT_c if self.phi_crossing else None

        lines = ["=" * 70]
        lines.append("phi Binder U_4  (phi = (M_right - M_left) / M_total)")
        header = f"{'kT':>7}  " + "  ".join(f"N={n:>3}" for n in n_values)
        sep = "-" * len(header)
        lines += [header, sep]

        for i, kT in enumerate(self.kT_values):
            row_parts = [f"{kT:7.4f}  "]
            for sweep in self.phi_sweeps:
                pt = sweep.points[i]
                if pt.error is not None:
                    row_parts.append(f"{'ERR':>7}")
                else:
                    row_parts.append(f"{pt.u4:>7.4f}")
            row = "  ".join(row_parts)
            if kT_c is not None:
                idx_closest = int(np.argmin(np.abs(kT_arr - kT_c)))
                if i == idx_closest:
                    row += f"  <-- T_c ≈ {kT_c:.4f}"
            lines.append(row)
        lines.append(sep)

        # Chi_phi peaks
        lines.append("\nSusceptibility peaks chi_phi = N*Var(phi):")
        lines.append(f"  {'N':>4}  {'kT_chi_peak':>11}  {'chi_max':>9}")
        for n, kT_peak, chi_max in self.chi_phi_peaks:
            if math.isnan(kT_peak):
                lines.append(f"  {n:>4}  {'---':>11}  {'---':>9}")
            else:
                lines.append(f"  {n:>4}  {kT_peak:>11.4f}  {chi_max:>9.4f}")

        # Crossing summary
        if self.phi_crossing:
            c = self.phi_crossing
            lines.append(f"\nBinder crossing ({c.method}):")
            lines.append(f"  T_c = {c.kT_c:.4f}  [lo={c.kT_lo:.4f}, hi={c.kT_hi:.4f}]")
            lines.append(f"  U_4 at T_c = {c.u4_c:.4f}")
            lines.append(f"  Representative pair: N={c.n_crossing[0]}, N={c.n_crossing[1]}")
        else:
            lines.append("\nNo phi Binder crossing found in kT range.")
            lines.append("  -> Adjust kT_values or density; or T_c is outside this range.")

        # Lambda_max table
        lines.append("\n" + "=" * 70)
        lines.append("Lambda_max  (open-BC approximation)")
        lya_header = f"{'kT':>7}  " + "  ".join(f"N={n:>3}" for n in n_values)
        lines += [lya_header, "-" * len(lya_header)]

        for i, kT in enumerate(self.kT_values):
            row_parts = [f"{kT:7.4f}  "]
            for sweep in self.lya_sweeps:
                pt = sweep.points[i]
                if pt.error is not None:
                    row_parts.append(f"{'ERR':>7}")
                elif math.isfinite(pt.lambda_max):
                    row_parts.append(f"{pt.lambda_max:>+7.4f}")
                else:
                    row_parts.append(f"{'nan':>7}")
            lines.append("  ".join(row_parts))
        lines.append("-" * len(lya_header))

        # Chaos boundaries
        lines.append("\nChaos boundary (kT where lambda_max = 0):")
        for n, kT_chaos in self.chaos_boundaries:
            if kT_chaos is None:
                lines.append(f"  N={n:>3}:  not found in kT range")
            else:
                lines.append(f"  N={n:>3}:  kT_chaos = {kT_chaos:.4f}")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main sweep
# ---------------------------------------------------------------------------

def scan_phi(
    n_values: tuple[int, ...] = (5, 10, 15, 20),
    kT_values: tuple[float, ...] | None = None,
    *,
    density: float = 16.67,
    gamma: float = 0.1,
    m_per_agent: float = 8.0,
    budget_per_agent: float = 2.0,
    n_steps: int = 800,
    concept_force: float = 0.3,
    seed: int = 0,
    k_conf: float = 0.0,
    ness_window: int = 30,
    lyapunov_steps: int = 300,
) -> PhiScan:
    """Run phi Binder sweep and Lyapunov sweep for each N at fixed density.

    Parameters
    ----------
    n_values:
        System sizes. Default (5, 10, 15, 20) at density=16.67 stays in
        all-attractive PBC regime (L/2 < 0.8 for all N).
    kT_values:
        Default: 20 log-spaced from 0.05 to 10.0 — extended range to
        capture the lambda_max = 0 chaos boundary.
    n_steps:
        Simulation steps for phi Binder sweep. More than binder_sweep()
        default for better phi statistics.
    lyapunov_steps:
        Steps for Benettin Lyapunov estimate at each (N, kT) point.
    """
    if kT_values is None:
        kT_values = tuple(np.geomspace(0.05, 10.0, 20).tolist())

    phi_sweeps: list[BinderSweep] = []
    lya_sweeps: list[LyapunovSweep] = []

    for n in n_values:
        phi_sweeps.append(phi_binder_sweep(
            n, kT_values,
            density=density,
            gamma=gamma,
            m_per_agent=m_per_agent,
            budget_per_agent=budget_per_agent,
            n_steps=n_steps,
            concept_force=concept_force,
            seed=seed,
            k_conf=k_conf,
            ness_window=ness_window,
        ))
        lya_sweeps.append(lyapunov_sweep(
            n, kT_values,
            density=density,
            gamma=gamma,
            m_per_agent=m_per_agent,
            budget_per_agent=budget_per_agent,
            n_steps=lyapunov_steps,
            concept_force=concept_force,
            seed=seed,
            k_conf=k_conf,
            ness_window=ness_window,
        ))

    phi_crossing = find_crossing(phi_sweeps)
    chi_phi_peaks = [
        (sweep.n_agents, *susceptibility_peak(sweep))
        for sweep in phi_sweeps
    ]
    chaos_boundaries = [
        (sweep.n_agents, sweep.chaos_boundary())
        for sweep in lya_sweeps
    ]

    return PhiScan(
        phi_sweeps=phi_sweeps,
        lya_sweeps=lya_sweeps,
        phi_crossing=phi_crossing,
        chi_phi_peaks=chi_phi_peaks,
        chaos_boundaries=chaos_boundaries,
        density=density,
        kT_values=list(kT_values),
        n_steps=n_steps,
    )

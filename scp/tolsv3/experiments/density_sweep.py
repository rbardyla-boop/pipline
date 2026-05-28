"""
density_sweep — Scientific experiment for Part XVII (Experiment 2).

Fixes N and sweeps density to cross L/2 = r_c independently of N scaling.

This is the cleaner topological control: N stays fixed, so finite-size effects
are constant while only geometry changes. Both geometry_scan and density_sweep
must show the same λ_max signature at the same L/2r_c to confirm the
topological interpretation.

Default: N=10, density from 4.0 to 25.0 (16 log-spaced values).
Topology threshold at density = N/(2*r_c) = 10/1.6 = 6.25 for N=10.

At low density (large L): L/2 > r_c → repulsive pairs appear.
At high density (small L): L/2 < r_c → all pairs attractive.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from entropy_lab.dwell_times import DwellStats, extract_dwell_times, fit_dwell_distribution
from entropy_lab.lyapunov import estimate_lyapunov
from entropy_lab.scaling_observables import binder_phi_cumulant, susceptibility_from_phi_trace
from entropy_lab.thermodynamic_limit import DensityPreservingSandbox

_R_C: float = 0.8


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DensitySweepPoint:
    density: float
    box_length: float          # L = N / density
    half_box_over_rc: float    # L/(2*r_c)
    lambda_max: float
    u4_phi: float
    chi_phi: float
    phase: str
    dwell_stats: DwellStats | None
    lambda_error: str | None
    phi_error: str | None


@dataclass(frozen=True)
class DensitySweep:
    points: list[DensitySweepPoint]
    n_agents: int
    kT: float
    n_steps_phi: int
    n_steps_lya: int

    def topology_threshold_density(self) -> float:
        """density at which L/2 = r_c: rho = N / (2 * r_c)."""
        return self.n_agents / (2.0 * _R_C)

    def lambda_array(self) -> np.ndarray:
        return np.array([p.lambda_max for p in self.points], dtype=float)

    def density_array(self) -> np.ndarray:
        return np.array([p.density for p in self.points], dtype=float)

    def dlambda_ddensity(self) -> np.ndarray:
        """Numerical derivative dλ/d(density) via central differences."""
        lam = self.lambda_array()
        rho = self.density_array()
        return np.gradient(lam, rho)

    def ascii_table(self) -> str:
        threshold_rho = self.topology_threshold_density()
        dlam = self.dlambda_ddensity()

        lines = [
            "=" * 80,
            f"Density Sweep  N={self.n_agents}  kT={self.kT}  "
            f"r_c={_R_C}  threshold at density≈{threshold_rho:.2f}",
            f"  (L/2r_c < 1: all attractive | L/2r_c > 1: repulsive pairs appear)",
            "",
            f"{'density':>8}  {'L/2r_c':>7}  {'λ_max':>8}  {'dλ/dρ':>8}  {'U_4(φ)':>8}  phase",
            "-" * 80,
        ]

        for i, pt in enumerate(self.points):
            lam_str = f"{pt.lambda_max:>8.4f}" if pt.lambda_error is None else f"{'ERR':>8}"
            dl_str = (
                f"{dlam[i]:>+8.4f}"
                if pt.lambda_error is None and math.isfinite(pt.lambda_max)
                else f"{'---':>8}"
            )
            u4_str = f"{pt.u4_phi:>8.4f}" if pt.phi_error is None else f"{'ERR':>8}"

            marker = ""
            if abs(pt.density - threshold_rho) / threshold_rho < 0.08:
                marker = "  ← topology threshold"
            elif pt.half_box_over_rc > 1.0 and (i == 0 or self.points[i - 1].half_box_over_rc <= 1.0):
                marker = "  ← first repulsive-pair density"

            lines.append(
                f"{pt.density:>8.2f}  {pt.half_box_over_rc:>7.3f}  "
                f"{lam_str}  {dl_str}  {u4_str}  {pt.phase}{marker}"
            )

        lines.append("=" * 80)

        # Dwell-time summary
        lines.append("\nDwell-time distribution per density:")
        lines.append(f"  {'density':>8}  {'crossings':>9}  {'mean_τ':>7}  fit          params")
        lines.append("  " + "-" * 56)
        for pt in self.points:
            ds = pt.dwell_stats
            if ds is None:
                lines.append(f"  {pt.density:>8.2f}  {'---':>9}  {'---':>7}  ---")
                continue
            if ds.fit_type == "insufficient_data":
                lines.append(
                    f"  {pt.density:>8.2f}  {ds.n_crossings:>9}  {ds.mean_dwell:>7.1f}  insufficient"
                )
            elif ds.fit_type == "exponential" and ds.fit_params:
                lines.append(
                    f"  {pt.density:>8.2f}  {ds.n_crossings:>9}  {ds.mean_dwell:>7.1f}  "
                    f"exponential  λ={ds.fit_params[0]:.4f}"
                )
            else:
                alpha = ds.fit_params[0] if ds.fit_params else float("nan")
                lines.append(
                    f"  {pt.density:>8.2f}  {ds.n_crossings:>9}  {ds.mean_dwell:>7.1f}  "
                    f"power_law    α={alpha:.4f}"
                )

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Per-point measurement
# ---------------------------------------------------------------------------

def _measure_point(
    density: float,
    n: int,
    kT: float,
    *,
    gamma: float,
    m_per_agent: float,
    budget_per_agent: float,
    n_steps_phi: int,
    n_steps_lya: int,
    concept_force: float,
    seed: int,
    k_conf: float,
    ness_window: int,
    tail_fraction: float,
    renorm_every: int,
) -> DensitySweepPoint:
    L = n / density
    half_box_over_rc = (L / 2.0) / _R_C
    budget = float(budget_per_agent * n)

    lambda_max = float("nan")
    lambda_error: str | None = None
    u4_phi = float("nan")
    chi_phi = float("nan")
    phi_error: str | None = None
    phase = "UNKNOWN"
    dwell_stats: DwellStats | None = None

    try:
        with np.errstate(over="raise", invalid="raise"):
            sb = DensityPreservingSandbox(
                n_agents=n, density=density, kT_global=kT, gamma=gamma,
                entropy_budget=budget, seed=seed, m_per_agent=m_per_agent,
                k_conf=k_conf, ness_window=ness_window,
            )
            report, trace = sb.simulate_full(n_steps_phi, concept_force)
        phase = report.phase_state.name
        u4_phi = binder_phi_cumulant(trace, tail_fraction).u4
        chi_phi = susceptibility_from_phi_trace(trace, n, tail_fraction)
        dts = extract_dwell_times(trace.phi_series)
        dwell_stats = fit_dwell_distribution(dts)
    except Exception as exc:
        phi_error = str(exc)[:80]
        phase = "ERROR"

    try:
        with np.errstate(over="raise", invalid="raise"):
            sb_lya = DensityPreservingSandbox(
                n_agents=n, density=density, kT_global=kT, gamma=gamma,
                entropy_budget=budget, seed=seed, m_per_agent=m_per_agent,
                k_conf=k_conf, ness_window=ness_window,
            )
            lya = estimate_lyapunov(
                sb_lya,
                n_steps=n_steps_lya,
                concept_force=concept_force,
                renorm_every=renorm_every,
            )
        lambda_max = lya.max_lyapunov
    except Exception as exc:
        lambda_error = str(exc)[:80]

    return DensitySweepPoint(
        density=density,
        box_length=L,
        half_box_over_rc=half_box_over_rc,
        lambda_max=lambda_max,
        u4_phi=u4_phi,
        chi_phi=chi_phi,
        phase=phase,
        dwell_stats=dwell_stats,
        lambda_error=lambda_error,
        phi_error=phi_error,
    )


# ---------------------------------------------------------------------------
# Main sweep
# ---------------------------------------------------------------------------

def scan_density_geometry(
    density_values: tuple[float, ...] | None = None,
    *,
    n_agents: int = 10,
    kT: float = 0.5,
    gamma: float = 0.1,
    m_per_agent: float = 8.0,
    budget_per_agent: float = 2.0,
    n_steps_phi: int = 1200,
    n_steps_lya: int = 300,
    concept_force: float = 0.3,
    seed: int = 0,
    k_conf: float = 0.0,
    ness_window: int = 30,
    tail_fraction: float = 0.5,
    renorm_every: int = 20,
) -> DensitySweep:
    """Sweep density at fixed N to probe the L/2r_c topology threshold.

    Parameters
    ----------
    density_values:
        Default: 16 log-spaced values from 4.0 to 25.0 for N=10.
        Threshold at density=6.25 (L/2 = r_c). Below 6.25: repulsive pairs.
    n_agents:
        Fixed system size. Default 10; use the same N as in geometry_scan
        so results can be overlaid on the same L/2r_c axis.
    kT:
        Temperature. Match geometry_scan kT for direct comparison.
    """
    if density_values is None:
        density_values = tuple(np.geomspace(4.0, 25.0, 16).tolist())

    points = [
        _measure_point(
            rho, n_agents, kT,
            gamma=gamma, m_per_agent=m_per_agent,
            budget_per_agent=budget_per_agent, n_steps_phi=n_steps_phi,
            n_steps_lya=n_steps_lya, concept_force=concept_force,
            seed=seed, k_conf=k_conf, ness_window=ness_window,
            tail_fraction=tail_fraction, renorm_every=renorm_every,
        )
        for rho in density_values
    ]

    return DensitySweep(
        points=points,
        n_agents=n_agents,
        kT=kT,
        n_steps_phi=n_steps_phi,
        n_steps_lya=n_steps_lya,
    )

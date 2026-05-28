"""
geometry_scan — Primary scientific experiment for Part XVII (Experiment 1).

Sweeps N at fixed density to cross the interaction-graph topology threshold
L/2 = r_c = 0.8 (N_crit ≈ 27 at density=16.67).

Measures per N:
  - lambda_max:  Lyapunov exponent (chaotic intensity)
  - dλ/dN:       numerical derivative — slope changes reveal transition sharpness
  - U_4(phi):    Binder cumulant of mass-asymmetry order parameter
  - phase:       NESS / FROZEN / METASTABLE / RUNAWAY
  - dwell times: phi residence-time statistics (exponential vs power-law)

The topology control variable L/2r_c is displayed explicitly so that results
from different density settings can be compared on the same axis.

Hypothesis test:
  A (geometric):     lambda_max jumps discontinuously at L/2r_c = 1.0 (N≈27)
  B (redistribution): lambda_max rises before N≈27, tracks FROZEN onset not geometry
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from entropy_lab.dwell_times import DwellStats, extract_dwell_times, fit_dwell_distribution
from entropy_lab.lyapunov import estimate_lyapunov
from entropy_lab.observables import PhysicsTrace
from entropy_lab.scaling_observables import binder_phi_cumulant, susceptibility_from_phi_trace
from entropy_lab.thermodynamic_limit import DensityPreservingSandbox

_R_C: float = 0.8   # repulsion threshold from lagrangian.py


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GeometryPoint:
    n_agents: int
    box_length: float          # L = N / density
    half_box_over_rc: float    # L/(2*r_c) — topology control variable; >1 means repulsive pairs appear
    lambda_max: float          # nan on error
    u4_phi: float              # Binder U_4(phi)
    chi_phi: float             # N * Var(phi)
    phase: str                 # PhaseState.name or "ERROR"
    dwell_stats: DwellStats | None
    lambda_error: str | None
    phi_error: str | None


@dataclass(frozen=True)
class GeometryScan:
    points: list[GeometryPoint]
    density: float
    kT: float
    n_steps_phi: int
    n_steps_lya: int

    def topology_threshold_N(self) -> float:
        """N at which L/2 = r_c: N = 2 * density * r_c."""
        return 2.0 * self.density * _R_C

    def lambda_array(self) -> np.ndarray:
        return np.array([p.lambda_max for p in self.points], dtype=float)

    def n_array(self) -> np.ndarray:
        return np.array([p.n_agents for p in self.points], dtype=float)

    def dlambda_dN(self) -> np.ndarray:
        """Numerical derivative dλ/dN via central differences.

        Slope spikes reveal the transition more clearly than raw λ_max.
        """
        lam = self.lambda_array()
        N = self.n_array()
        return np.gradient(lam, N)

    def ascii_table(self) -> str:
        threshold_N = self.topology_threshold_N()
        dlam = self.dlambda_dN()

        lines = [
            "=" * 78,
            f"Geometry Scan  density={self.density}  kT={self.kT}  "
            f"r_c={_R_C}  threshold at N≈{threshold_N:.1f}",
            f"  (L/2r_c < 1: all attractive | L/2r_c > 1: repulsive pairs appear)",
            "",
            f"{'N':>5}  {'L/2r_c':>7}  {'λ_max':>8}  {'dλ/dN':>8}  {'U_4(φ)':>8}  phase",
            "-" * 78,
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
            if abs(pt.n_agents - threshold_N) < 1.5:
                marker = "  ← topology threshold"
            elif pt.half_box_over_rc > 1.0 and (i == 0 or self.points[i - 1].half_box_over_rc <= 1.0):
                marker = "  ← first repulsive-pair N"

            lines.append(
                f"{pt.n_agents:>5}  {pt.half_box_over_rc:>7.3f}  "
                f"{lam_str}  {dl_str}  {u4_str}  {pt.phase}{marker}"
            )

        lines.append("=" * 78)

        # Dwell-time summary
        lines.append("\nDwell-time distribution per N:")
        lines.append(f"  {'N':>4}  {'crossings':>9}  {'mean_τ':>7}  fit          params")
        lines.append("  " + "-" * 52)
        for pt in self.points:
            ds = pt.dwell_stats
            if ds is None:
                lines.append(f"  {pt.n_agents:>4}  {'---':>9}  {'---':>7}  ---")
                continue
            if ds.fit_type == "insufficient_data":
                lines.append(
                    f"  {pt.n_agents:>4}  {ds.n_crossings:>9}  {ds.mean_dwell:>7.1f}  insufficient"
                )
            elif ds.fit_type == "exponential" and ds.fit_params:
                lines.append(
                    f"  {pt.n_agents:>4}  {ds.n_crossings:>9}  {ds.mean_dwell:>7.1f}  "
                    f"exponential  λ={ds.fit_params[0]:.4f}"
                )
            elif ds.fit_type == "power_law":
                lines.append(
                    f"  {pt.n_agents:>4}  {ds.n_crossings:>9}  {ds.mean_dwell:>7.1f}  "
                    f"power_law    α={ds.fit_params[0]:.4f}"
                )
            else:
                lines.append(
                    f"  {pt.n_agents:>4}  {ds.n_crossings:>9}  {ds.mean_dwell:>7.1f}  {ds.fit_type}"
                )

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Per-point measurement (2 sims: simulate_full + estimate_lyapunov)
# ---------------------------------------------------------------------------

def _measure_point(
    n: int,
    kT: float,
    *,
    density: float,
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
) -> GeometryPoint:
    L = n / density
    half_box_over_rc = (L / 2.0) / _R_C

    lambda_max = float("nan")
    lambda_error: str | None = None
    u4_phi = float("nan")
    chi_phi = float("nan")
    phi_error: str | None = None
    phase = "UNKNOWN"
    dwell_stats: DwellStats | None = None

    budget = float(budget_per_agent * n)

    # --- phi observables from simulate_full ---
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

    # --- Lyapunov from fresh same-seed sandbox ---
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
        if phase == "UNKNOWN":
            phase = "NESS"  # no phase info from Lyapunov run alone
    except Exception as exc:
        lambda_error = str(exc)[:80]

    return GeometryPoint(
        n_agents=n,
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

def scan_geometry(
    n_values: tuple[int, ...] | None = None,
    *,
    density: float = 16.67,
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
) -> GeometryScan:
    """Sweep N at fixed density to probe the L/2r_c topology threshold.

    Parameters
    ----------
    n_values:
        Default: range(5, 36, 2) — 16 points from N=5 to N=35.
        Crosses the topology threshold at N≈27 (L/2 = r_c = 0.8).
    kT:
        Temperature. Run at kT=0.5 (baseline) and kT=2.0 (higher) to
        test whether the λ_max anomaly tracks phase or geometry.
    n_steps_phi:
        Steps for simulate_full() (phi observables + dwell times).
        Longer than Part XVI to reduce phi Binder noise.
    n_steps_lya:
        Steps for estimate_lyapunov() Benettin algorithm.
    """
    if n_values is None:
        n_values = tuple(range(5, 36, 2))

    points = [
        _measure_point(
            n, kT,
            density=density, gamma=gamma, m_per_agent=m_per_agent,
            budget_per_agent=budget_per_agent, n_steps_phi=n_steps_phi,
            n_steps_lya=n_steps_lya, concept_force=concept_force,
            seed=seed, k_conf=k_conf, ness_window=ness_window,
            tail_fraction=tail_fraction, renorm_every=renorm_every,
        )
        for n in n_values
    ]

    return GeometryScan(
        points=points,
        density=density,
        kT=kT,
        n_steps_phi=n_steps_phi,
        n_steps_lya=n_steps_lya,
    )

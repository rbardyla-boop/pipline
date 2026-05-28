"""
thermal_geometry_scan — Part XVIII (Sprint 1).

Tests the thermal fluctuation length hypothesis:

    L_crit  ∝  sqrt(kT / K_eff)
    ⟺  rho_crit * sqrt(kT / K_eff)  =  const

Procedure for each kT value:
  1. Run a density sweep (fixed N, vary rho) to measure lambda_max(rho).
  2. Find rho_crit = density of maximum |dlambda/drho| (transition signature).
  3. Run a short simulation at rho_crit to measure K_eff from NESS mass variance.
  4. Compute scaled_rho = rho_crit * sqrt(kT/K_eff).

Predictions anchored at kT=0.5 (empirical rho_crit ≈ 8.33, K_eff ≈ 0.8):
  scaled_rho_ref  ≈ 8.33 * sqrt(0.5/0.8)  ≈ 6.59
  kT=0.1 → rho_crit ≈ 18.6   (higher density needed for colder system)
  kT=0.3 → rho_crit ≈ 10.8
  kT=1.0 → rho_crit ≈  5.9
  kT=2.0 → rho_crit ≈  4.2
  kT=4.0 → rho_crit ≈  2.9   (may fall below default density range)
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from entropy_lab.scaling_collapse import (
    CollapseResult,
    compute_collapse,
    find_critical_density,
    mean_coupling_from_trace,
)
from entropy_lab.thermodynamic_limit import DensityPreservingSandbox

try:
    from .density_sweep import DensitySweep, scan_density_geometry
except ImportError:
    from density_sweep import DensitySweep, scan_density_geometry  # type: ignore[no-redef]


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ThermalScanPoint:
    kT: float
    sweep: DensitySweep           # full density sweep at this kT
    rho_crit: float | None        # None if no transition found in density range
    L_crit: float | None          # n_agents / rho_crit
    K_eff: float | None           # NESS coupling from trace at rho_crit
    L_th: float | None            # sqrt(kT / K_eff)
    scaled_rho: float | None      # rho_crit * sqrt(kT/K_eff); const if hypothesis holds
    keff_error: str | None        # non-None if K_eff measurement failed


@dataclass(frozen=True)
class ThermalGeometryScan:
    points: list[ThermalScanPoint]
    n_agents: int
    M_total: float
    collapse: CollapseResult | None   # None if < 2 transition points found

    def stratified_collapse(self, phase: str) -> CollapseResult | None:
        """Collapse using only kT points whose ρ_crit lies in a given phase region.

        For each ThermalScanPoint, the DensitySweepPoint closest to rho_crit
        determines the phase at that density. Only points where that phase matches
        the requested phase are included in the collapse input.

        Valid phase values: "NESS", "FROZEN", "METASTABLE", "RUNAWAY", "DIFFUSIVE".
        Returns None if fewer than 2 points qualify.
        """
        raw: list[tuple[float, float, float]] = []
        for pt in self.points:
            if pt.rho_crit is None or pt.K_eff is None:
                continue
            if not pt.sweep.points:
                continue
            closest = min(pt.sweep.points, key=lambda p: abs(p.density - pt.rho_crit))
            if closest.phase == phase:
                raw.append((pt.kT, pt.rho_crit, pt.K_eff))
        if len(raw) < 2:
            return None
        return compute_collapse(raw, self.n_agents)

    def ascii_table(self) -> str:
        lines = [
            "=" * 86,
            f"Thermal Geometry Scan  N={self.n_agents}  M_total={self.M_total:.1f}",
            f"  Hypothesis: rho_crit * sqrt(kT / K_eff) = const",
            f"  Confirmed when collapse_quality > 0.85  (std/mean < 0.15)",
            "",
            f"{'kT':>7}  {'rho_crit':>9}  {'L_crit':>7}  {'K_eff':>7}  "
            f"{'L_th':>7}  {'scaled_rho':>10}  note",
            "-" * 86,
        ]

        for pt in self.points:
            kT_str = f"{pt.kT:>7.3f}"
            if pt.rho_crit is None:
                lines.append(
                    f"{kT_str}  {'---':>9}  {'---':>7}  {'---':>7}  "
                    f"{'---':>7}  {'---':>10}  no transition in scan range"
                )
                continue

            rho_s = f"{pt.rho_crit:>9.3f}"
            Lc_s = f"{pt.L_crit:>7.4f}"
            Ke_s = f"{pt.K_eff:>7.4f}" if pt.K_eff is not None else f"{'ERR':>7}"
            Lt_s = f"{pt.L_th:>7.4f}" if pt.L_th is not None else f"{'---':>7}"
            sr_s = (
                f"{pt.scaled_rho:>10.4f}"
                if pt.scaled_rho is not None
                else f"{'---':>10}"
            )
            note = ""
            if pt.keff_error:
                note = f"  K_eff ERR: {pt.keff_error[:35]}"
            lines.append(
                f"{kT_str}  {rho_s}  {Lc_s}  {Ke_s}  {Lt_s}  {sr_s}{note}"
            )

        lines.append("=" * 86)

        if self.collapse is None:
            lines.append(
                "\nCollapse analysis: insufficient data (< 2 transition points found)"
            )
            lines.append(
                "  → Extend density_values range or increase n_steps_lya for more signal."
            )
        else:
            c = self.collapse
            ratio = (
                f"{c.std_scaled_rho / c.mean_scaled_rho:.3f}"
                if c.mean_scaled_rho > 1e-9
                else "---"
            )
            verdict = "CONFIRMED" if c.is_collapsed() else "REJECTED"
            lines += [
                f"\nCollapse analysis ({len(c.points)} points):",
                f"  mean(rho_crit * sqrt(kT/K_eff)) = {c.mean_scaled_rho:.4f}",
                f"  std(rho_crit * sqrt(kT/K_eff))  = {c.std_scaled_rho:.4f}",
                f"  std / mean                       = {ratio}",
                f"  collapse_quality (1 - std/mean)  = {c.collapse_quality:.4f}",
                f"  Thermal scaling hypothesis: {verdict}",
            ]
            if not c.is_collapsed():
                lines.append(
                    "  → Transition does not scale as sqrt(kT/K_eff); "
                    "K_eff may be kT-dependent or mechanism is non-thermal."
                )

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main scan
# ---------------------------------------------------------------------------

def scan_thermal_geometry(
    kT_values: tuple[float, ...] = (0.1, 0.3, 0.5, 1.0, 2.0, 4.0),
    *,
    n_agents: int = 10,
    density_values: tuple[float, ...] | None = None,
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
    keff_n_steps: int = 400,
) -> ThermalGeometryScan:
    """Sweep density at each kT to test the thermal fluctuation length hypothesis.

    Parameters
    ----------
    kT_values:
        Temperatures to probe. Default spans a decade around the empirical
        kT=0.5 baseline. Predictions: rho_crit ≈ 18.6 at kT=0.1,
        rho_crit ≈ 4.2 at kT=2.0.
    density_values:
        Density range for each sub-sweep. Default: 16 log-spaced from 2.0 to
        25.0 — wider than the Part XVII default to cover high-kT transitions.
        If kT=0.1 transition is missed (no rho_crit found), extend to 30.
    keff_n_steps:
        Steps for the dedicated NESS simulation at rho_crit to measure K_eff.
        400 steps is sufficient since only mass_variance tail is needed.
    """
    if density_values is None:
        density_values = tuple(np.geomspace(2.0, 25.0, 16).tolist())

    M_total = m_per_agent * n_agents
    points: list[ThermalScanPoint] = []

    for kT in kT_values:
        sweep = scan_density_geometry(
            density_values=density_values,
            n_agents=n_agents,
            kT=kT,
            gamma=gamma,
            m_per_agent=m_per_agent,
            budget_per_agent=budget_per_agent,
            n_steps_phi=n_steps_phi,
            n_steps_lya=n_steps_lya,
            concept_force=concept_force,
            seed=seed,
            k_conf=k_conf,
            ness_window=ness_window,
            tail_fraction=tail_fraction,
            renorm_every=renorm_every,
        )

        crit = find_critical_density(sweep.lambda_array(), sweep.density_array())
        if crit is None:
            points.append(ThermalScanPoint(
                kT=kT, sweep=sweep,
                rho_crit=None, L_crit=None, K_eff=None,
                L_th=None, scaled_rho=None, keff_error=None,
            ))
            continue

        rho_crit, _ = crit
        L_crit = float(n_agents) / rho_crit

        # Short dedicated simulation at rho_crit to measure NESS K_eff
        K_eff: float | None = None
        keff_error: str | None = None
        try:
            with np.errstate(over="raise", invalid="raise"):
                sb = DensityPreservingSandbox(
                    n_agents=n_agents,
                    density=rho_crit,
                    kT_global=kT,
                    gamma=gamma,
                    entropy_budget=float(budget_per_agent * n_agents),
                    seed=seed,
                    m_per_agent=m_per_agent,
                    k_conf=k_conf,
                    ness_window=ness_window,
                )
                _, trace = sb.simulate_full(keff_n_steps, concept_force)
            K_eff = mean_coupling_from_trace(trace, n_agents, M_total, tail_fraction)
        except Exception as exc:
            keff_error = str(exc)[:60]

        L_th: float | None = None
        scaled_rho: float | None = None
        if K_eff is not None and K_eff > 1e-9:
            L_th = math.sqrt(kT / K_eff)
            scaled_rho = rho_crit * L_th

        points.append(ThermalScanPoint(
            kT=kT, sweep=sweep,
            rho_crit=rho_crit, L_crit=L_crit,
            K_eff=K_eff, L_th=L_th, scaled_rho=scaled_rho,
            keff_error=keff_error,
        ))

    # Collapse analysis across all kT values where transition was found
    raw = [
        (pt.kT, pt.rho_crit, pt.K_eff)
        for pt in points
        if pt.rho_crit is not None and pt.K_eff is not None
    ]
    collapse: CollapseResult | None = None
    if len(raw) >= 2:
        collapse = compute_collapse(raw, n_agents)

    return ThermalGeometryScan(
        points=points, n_agents=n_agents, M_total=M_total, collapse=collapse,
    )

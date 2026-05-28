"""
collapse_verification — Sprint 1 Verification orchestrator (Part XVIII).

Stress-tests the thermal scaling collapse result from Sprint 1 along four axes:

1. Specificity   — does ρ·√(kT/K_eff) outperform wrong scaling variables?
2. Finite-time   — does quality improve monotonically with n_steps_lya?
3. Stratification — does collapse hold within each phase independently?
4. Bootstrap     — is ρ_crit reproducible across seeds (CI width < 10%)?

Usage:
    from experiments.thermal_geometry_scan import scan_thermal_geometry
    from experiments.collapse_verification import run_collapse_verification

    base = scan_thermal_geometry(kT_values=(0.3, 0.5, 1.0, 2.0))
    v = run_collapse_verification(base, step_counts=(100, 200, 400, 800), n_seeds=0)
    print(v.ascii_table())
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from entropy_lab.scaling_collapse import (
    CollapseResult,
    CollapseSpecificity,
    alternative_scalings,
    compute_collapse,
    find_critical_density,
)

try:
    from .density_sweep import scan_density_geometry
    from .thermal_geometry_scan import ThermalGeometryScan
except ImportError:
    from density_sweep import scan_density_geometry  # type: ignore[no-redef]
    from thermal_geometry_scan import ThermalGeometryScan  # type: ignore[no-redef]


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FiniteTimeRow:
    n_steps_lya: int
    n_transitions_found: int   # how many kT values yielded a rho_crit
    collapse: CollapseResult | None


@dataclass(frozen=True)
class BootstrapRow:
    kT: float
    mean_rho_crit: float
    std_rho_crit: float
    ci_lower: float    # 2.5th percentile across seeds
    ci_upper: float    # 97.5th percentile across seeds
    n_seeds: int       # seeds that yielded a rho_crit (may be < n_seeds_requested)


@dataclass(frozen=True)
class CollapseVerification:
    base_scan: ThermalGeometryScan
    specificity: CollapseSpecificity
    finite_time: list[FiniteTimeRow]          # sorted ascending by n_steps_lya
    stratified: dict[str, CollapseResult | None]   # phase → collapse
    bootstrap_rows: list[BootstrapRow] | None      # None when n_seeds=0

    def ascii_table(self) -> str:
        lines: list[str] = []

        # ── Section 1: Scaling variable specificity ──────────────────────────
        lines += [
            "=" * 70,
            "SECTION 1 — Scaling Variable Specificity",
            "  Falsification: ρ·√(kT/K_eff) must rank #1 to support the hypothesis.",
            "",
            self.specificity.ascii_table(),
        ]
        name, q = self.specificity.best()
        verdict = "PASS" if name == "ρ·√(kT/K_eff)" else "FAIL"
        lines += [
            f"\n  Specificity verdict: {verdict}  (winner={name!r}, quality={q:.4f})",
        ]

        # ── Section 2: Finite-time stability ─────────────────────────────────
        lines += [
            "",
            "=" * 70,
            "SECTION 2 — Finite-Time Stability",
            "  Falsification: quality must be monotonically non-decreasing with n_steps_lya.",
            "",
            f"{'n_steps_lya':>12}  {'n_transitions':>13}  {'quality':>9}  {'collapsed?':>10}",
            "-" * 52,
        ]
        prev_q: float | None = None
        monotone = True
        for row in self.finite_time:
            if row.collapse is not None:
                q_s = f"{row.collapse.collapse_quality:>9.4f}"
                col_s = "YES" if row.collapse.is_collapsed() else "NO"
                if prev_q is not None and row.collapse.collapse_quality < prev_q - 0.01:
                    monotone = False
                prev_q = row.collapse.collapse_quality
            else:
                q_s = f"{'---':>9}"
                col_s = "---"
            lines.append(
                f"{row.n_steps_lya:>12}  {row.n_transitions_found:>13}  "
                f"{q_s}  {col_s:>10}"
            )
        ft_verdict = "PASS" if monotone else "FAIL (quality degraded past 0.01 between steps)"
        lines.append(f"\n  Finite-time verdict: {ft_verdict}")

        # ── Section 3: Phase-stratified collapse ──────────────────────────────
        lines += [
            "",
            "=" * 70,
            "SECTION 3 — Phase-Stratified Collapse",
            "  Falsification: NESS-only collapse quality should be ≥ full collapse quality.",
            "",
            f"{'phase':>12}  {'n_points':>8}  {'quality':>9}  {'collapsed?':>10}",
            "-" * 50,
        ]
        full_q = (
            self.base_scan.collapse.collapse_quality
            if self.base_scan.collapse is not None
            else float("nan")
        )
        for phase, result in self.stratified.items():
            if result is not None:
                q_s = f"{result.collapse_quality:>9.4f}"
                col_s = "YES" if result.is_collapsed() else "NO"
                n_s = f"{len(result.points):>8}"
            else:
                q_s = f"{'---':>9}"
                col_s = "---"
                n_s = f"{'0':>8}"
            lines.append(f"{phase:>12}  {n_s}  {q_s}  {col_s:>10}")
        lines.append(f"\n  Full-scan quality: {full_q:.4f}")

        # ── Section 4: Bootstrap stability ────────────────────────────────────
        if self.bootstrap_rows is not None:
            lines += [
                "",
                "=" * 70,
                "SECTION 4 — Seed Stability (Bootstrap CI on ρ_crit)",
                "  Falsification: std/mean < 0.10 at each kT → transition is reproducible.",
                "",
                f"{'kT':>6}  {'mean_ρ':>8}  {'std_ρ':>7}  {'std/mean':>9}  "
                f"{'CI_2.5%':>8}  {'CI_97.5%':>9}  {'n_seeds':>7}",
                "-" * 66,
            ]
            tight = True
            for row in self.bootstrap_rows:
                ratio = row.std_rho_crit / row.mean_rho_crit if row.mean_rho_crit > 1e-9 else float("nan")
                if math.isfinite(ratio) and ratio > 0.10:
                    tight = False
                ratio_s = f"{ratio:.4f}" if math.isfinite(ratio) else "---"
                lines.append(
                    f"{row.kT:>6.3f}  {row.mean_rho_crit:>8.3f}  {row.std_rho_crit:>7.3f}  "
                    f"{ratio_s:>9}  {row.ci_lower:>8.3f}  {row.ci_upper:>9.3f}  "
                    f"{row.n_seeds:>7}"
                )
            bs_verdict = "PASS" if tight else "FAIL (std/mean ≥ 0.10 at one or more kT)"
            lines.append(f"\n  Bootstrap verdict: {bs_verdict}")
        else:
            lines += [
                "",
                "=" * 70,
                "SECTION 4 — Seed Stability: skipped (n_seeds=0)",
                "  Run with n_seeds ≥ 5 to test reproducibility.",
            ]

        lines.append("=" * 70)
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main verification runner
# ---------------------------------------------------------------------------

def run_collapse_verification(
    base_scan: ThermalGeometryScan,
    *,
    step_counts: tuple[int, ...] = (100, 200, 400, 800),
    n_seeds: int = 0,
    density_values: tuple[float, ...] | None = None,
    gamma: float = 0.1,
    m_per_agent: float = 8.0,
    budget_per_agent: float = 2.0,
    n_steps_phi: int = 400,
    concept_force: float = 0.3,
    seed: int = 0,
    k_conf: float = 0.0,
    ness_window: int = 30,
    tail_fraction: float = 0.5,
    renorm_every: int = 20,
) -> CollapseVerification:
    """Run four-axis stress test on a base ThermalGeometryScan result.

    Parameters
    ----------
    base_scan:
        The ThermalGeometryScan from scan_thermal_geometry() whose collapse
        result is being verified. K_eff values are reused for finite-time rows.
    step_counts:
        n_steps_lya values to probe for finite-time stability.
    n_seeds:
        Number of seeds to run for bootstrap CI. 0 skips bootstrap (fast path).
    n_steps_phi:
        Steps for the phi measurement during finite-time sweeps. Lower than
        the base scan default (1200) since we only need rho_crit, not K_eff.
    """
    n_agents = base_scan.n_agents

    # ── Specificity ───────────────────────────────────────────────────────────
    valid_pts = [pt for pt in base_scan.points if pt.rho_crit is not None and pt.K_eff is not None]
    specificity = alternative_scalings(
        kT_values=[pt.kT for pt in valid_pts],
        rho_crits=[pt.rho_crit for pt in valid_pts],  # type: ignore[misc]
        K_eff_values=[pt.K_eff for pt in valid_pts],  # type: ignore[misc]
        n_agents=n_agents,
    )

    # ── Finite-time stability ─────────────────────────────────────────────────
    # Build (kT, K_eff) map from base_scan; K_eff is a NESS property, not
    # Lyapunov-step-dependent, so we reuse it across all step counts.
    keff_by_kT: dict[float, float] = {
        pt.kT: pt.K_eff
        for pt in base_scan.points
        if pt.K_eff is not None
    }

    finite_time: list[FiniteTimeRow] = []
    for n_steps_lya in sorted(step_counts):
        raw: list[tuple[float, float, float]] = []
        for kT, K_eff in keff_by_kT.items():
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
            if crit is not None:
                rho_crit, _ = crit
                raw.append((kT, rho_crit, K_eff))

        collapse: CollapseResult | None = None
        if len(raw) >= 2:
            collapse = compute_collapse(raw, n_agents)

        finite_time.append(FiniteTimeRow(
            n_steps_lya=n_steps_lya,
            n_transitions_found=len(raw),
            collapse=collapse,
        ))

    # ── Phase stratification ──────────────────────────────────────────────────
    phases = ["NESS", "FROZEN", "METASTABLE", "RUNAWAY", "DIFFUSIVE"]
    stratified: dict[str, CollapseResult | None] = {}
    for phase in phases:
        result = base_scan.stratified_collapse(phase)
        if result is not None or any(
            pt.rho_crit is not None and pt.K_eff is not None
            for pt in base_scan.points
        ):
            stratified[phase] = result

    # ── Bootstrap seed stability ──────────────────────────────────────────────
    bootstrap_rows: list[BootstrapRow] | None = None
    if n_seeds > 0:
        # per_kT: kT → list of rho_crit values across seeds
        per_kT: dict[float, list[float]] = {pt.kT: [] for pt in base_scan.points}

        for s in range(n_seeds):
            for pt in base_scan.points:
                sweep = scan_density_geometry(
                    density_values=density_values,
                    n_agents=n_agents,
                    kT=pt.kT,
                    gamma=gamma,
                    m_per_agent=m_per_agent,
                    budget_per_agent=budget_per_agent,
                    n_steps_phi=n_steps_phi,
                    n_steps_lya=200,
                    concept_force=concept_force,
                    seed=s,
                    k_conf=k_conf,
                    ness_window=ness_window,
                    tail_fraction=tail_fraction,
                    renorm_every=renorm_every,
                )
                crit = find_critical_density(sweep.lambda_array(), sweep.density_array())
                if crit is not None:
                    per_kT[pt.kT].append(crit[0])

        bootstrap_rows = []
        for kT in sorted(per_kT.keys()):
            samples = per_kT[kT]
            if len(samples) < 2:
                continue
            arr = np.array(samples, dtype=float)
            bootstrap_rows.append(BootstrapRow(
                kT=kT,
                mean_rho_crit=float(arr.mean()),
                std_rho_crit=float(arr.std()),
                ci_lower=float(np.percentile(arr, 2.5)),
                ci_upper=float(np.percentile(arr, 97.5)),
                n_seeds=len(samples),
            ))

    return CollapseVerification(
        base_scan=base_scan,
        specificity=specificity,
        finite_time=finite_time,
        stratified=stratified,
        bootstrap_rows=bootstrap_rows,
    )


__all__ = [
    "FiniteTimeRow",
    "BootstrapRow",
    "CollapseVerification",
    "run_collapse_verification",
]

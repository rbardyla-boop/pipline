"""
Falsification tests for Sprint 1 verification:
  - entropy_lab.scaling_collapse.alternative_scalings / CollapseSpecificity
  - experiments.thermal_geometry_scan.ThermalGeometryScan.stratified_collapse
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from entropy_lab.scaling_collapse import (
    CollapseSpecificity,
    CollapseResult,
    alternative_scalings,
    compute_collapse,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _perfect_correct_data(
    kT_vals: list[float],
    K_effs: list[float],
    C: float = 6.0,
) -> tuple[list[float], list[float], list[float]]:
    """Generate (kT_vals, rho_crits, K_effs) where ρ·√(kT/K_eff) = C exactly."""
    rho_crits = [C / math.sqrt(kT / K) for kT, K in zip(kT_vals, K_effs)]
    return kT_vals, rho_crits, K_effs


# ---------------------------------------------------------------------------
# Test 1: Correct variable wins for varying K_eff
# ---------------------------------------------------------------------------

def test_alternative_scalings_correct_wins():
    """ρ·√(kT/K_eff) should score quality=1.0 and rank #1 when K_eff varies with kT."""
    # K_eff varies → ρ·√kT will NOT be constant (it equals C·√K_eff which varies)
    kT_vals = [0.1, 0.5, 1.0, 2.0, 4.0]
    K_effs  = [0.70, 0.75, 0.80, 0.88, 0.96]   # rises with kT
    kT_vals, rho_crits, K_effs = _perfect_correct_data(kT_vals, K_effs)

    spec = alternative_scalings(kT_vals, rho_crits, K_effs, n_agents=10)
    name, quality = spec.best()
    assert name == "ρ·√(kT/K_eff)", f"Wrong winner: {name!r}, quality={quality}"
    assert abs(quality - 1.0) < 1e-9, f"Correct variable quality should be 1.0, got {quality}"


# ---------------------------------------------------------------------------
# Test 2: Wrong variables score strictly below 1.0 when K_eff varies
# ---------------------------------------------------------------------------

def test_alternative_scalings_wrong_variables_lower():
    """All wrong variables score < 0.99 when K_eff has genuine variation across kT."""
    kT_vals = [0.1, 0.5, 1.0, 2.0, 4.0]
    K_effs  = [0.70, 0.75, 0.80, 0.88, 0.96]
    kT_vals, rho_crits, K_effs = _perfect_correct_data(kT_vals, K_effs)

    spec = alternative_scalings(kT_vals, rho_crits, K_effs, n_agents=10)
    for name, result in spec.results.items():
        if name == "ρ·√(kT/K_eff)":
            continue
        assert result.collapse_quality < 0.99, (
            f"{name!r} should not collapse perfectly with varying K_eff; "
            f"quality={result.collapse_quality:.6f}"
        )


# ---------------------------------------------------------------------------
# Test 3: Uniform K_eff → both correct and ρ·√kT score 1.0
# ---------------------------------------------------------------------------

def test_alternative_scalings_uniform_K_eff_both_collapse():
    """When K_eff is uniform across kT, ρ·√kT scores equally to the correct variable.

    With K_eff = const K: ρ·√kT = C·√K (constant) since rho_crit = C/√(kT/K).
    This identifies when the K_eff measurement adds no discriminating information.
    """
    kT_vals = [0.1, 0.5, 1.0, 2.0, 4.0]
    K_effs  = [0.8] * 5   # UNIFORM K_eff
    kT_vals, rho_crits, K_effs = _perfect_correct_data(kT_vals, K_effs)

    spec = alternative_scalings(kT_vals, rho_crits, K_effs, n_agents=10)
    q_correct = spec.results["ρ·√(kT/K_eff)"].collapse_quality
    q_sqrtkT  = spec.results["ρ·√kT"].collapse_quality
    assert abs(q_correct - 1.0) < 1e-9, f"Correct quality={q_correct}"
    assert abs(q_sqrtkT  - 1.0) < 1e-9, (
        f"ρ·√kT should also collapse perfectly with uniform K_eff; quality={q_sqrtkT}"
    )


# ---------------------------------------------------------------------------
# Test 4: stratified_collapse selects by phase correctly
# ---------------------------------------------------------------------------

def test_stratified_collapse_by_phase():
    """NESS stratification returns all matching points; FROZEN returns None."""
    import math
    from experiments.density_sweep import DensitySweep, DensitySweepPoint
    from experiments.thermal_geometry_scan import ThermalGeometryScan, ThermalScanPoint

    kT_vals = [0.5, 1.0, 2.0]
    rho_crit_val = 8.0
    K_eff_val = 0.8

    def make_sweep(kT: float, phase: str = "NESS") -> DensitySweep:
        pt = DensitySweepPoint(
            density=rho_crit_val,
            box_length=float(10) / rho_crit_val,
            half_box_over_rc=rho_crit_val / (2.0 * 10 * 0.8),
            lambda_max=0.3,
            u4_phi=0.5,
            chi_phi=2.0,
            phase=phase,
            dwell_stats=None,
            lambda_error=None,
            phi_error=None,
        )
        return DensitySweep(
            points=[pt], n_agents=10, kT=kT, n_steps_phi=400, n_steps_lya=200
        )

    scan_points = [
        ThermalScanPoint(
            kT=kT,
            sweep=make_sweep(kT, phase="NESS"),
            rho_crit=rho_crit_val,
            L_crit=10.0 / rho_crit_val,
            K_eff=K_eff_val,
            L_th=math.sqrt(kT / K_eff_val),
            scaled_rho=rho_crit_val * math.sqrt(kT / K_eff_val),
            keff_error=None,
        )
        for kT in kT_vals
    ]
    full_collapse = compute_collapse(
        [(pt.kT, pt.rho_crit, pt.K_eff) for pt in scan_points], n_agents=10
    )
    scan = ThermalGeometryScan(
        points=scan_points, n_agents=10, M_total=80.0, collapse=full_collapse
    )

    # All 3 points have NESS phase → stratified_collapse("NESS") yields 3 points
    ness = scan.stratified_collapse("NESS")
    assert ness is not None, "Expected NESS collapse result, got None"
    assert len(ness.points) == 3, f"Expected 3 NESS points, got {len(ness.points)}"

    # No FROZEN points → stratified_collapse("FROZEN") returns None
    frozen = scan.stratified_collapse("FROZEN")
    assert frozen is None, f"Expected None for FROZEN, got {frozen}"

"""
scaling_collapse — Thermal fluctuation length hypothesis testing (Part XVIII / Sprint 1).

Hypothesis: the chaos transition occurs when the box half-length L/2 equals
the thermal fluctuation length L_th = sqrt(kT / K_eff):

    L_crit / L_th = const   across kT values
    ⟺  rho_crit * sqrt(kT / K_eff) = const

K_eff is the mean pairwise attractive coupling in the NESS phase.  It is
estimated from the mass-variance recorded in PhysicsTrace via the identity:

    Σ_{i≠j} m_i*m_j = M²(1-1/N) - N·Var(m)

so

    K_eff  =  M / N²  -  <Var(m)>_ness / (M · (N-1))

For uniform masses Var(m)=0 and K_eff = M/N² = m_per_agent/N (e.g. 0.8 for N=10).

Sprint 1 verification adds CollapseSpecificity and alternative_scalings() which test
whether the correct variable ρ·√(kT/K_eff) outperforms five wrong candidates.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

import numpy as np

from .observables import PhysicsTrace


@dataclass(frozen=True)
class CollapsePoint:
    kT: float
    rho_crit: float        # density at maximum |dλ/dρ|
    L_crit: float          # n_agents / rho_crit
    K_eff: float           # mean pairwise coupling from NESS trace
    L_th: float            # scaling factor applied (sqrt(kT/K_eff) for correct variable)
    scaled_rho: float      # rho_crit * L_th — should be const if hypothesis holds
    residual: float | None # |scaled_rho - mean_scaled_rho|, filled by _build_collapse_result


@dataclass(frozen=True)
class CollapseResult:
    points: list[CollapsePoint]
    mean_scaled_rho: float
    std_scaled_rho: float
    collapse_quality: float    # 1 - std/mean; 1.0 = perfect, < 0.85 = poor

    def is_collapsed(self, tolerance: float = 0.15) -> bool:
        """Return True when std(scaled_rho) / mean < tolerance."""
        if not math.isfinite(self.mean_scaled_rho) or self.mean_scaled_rho < 1e-9:
            return False
        return (self.std_scaled_rho / self.mean_scaled_rho) < tolerance


@dataclass(frozen=True)
class CollapseSpecificity:
    """Collapse quality for each of five scaling variable candidates."""
    results: dict[str, CollapseResult]   # variable name → CollapseResult

    def best(self) -> tuple[str, float]:
        """Return (name, quality) of the highest-quality variable."""
        name, result = max(self.results.items(), key=lambda kv: kv[1].collapse_quality)
        return name, result.collapse_quality

    def ascii_table(self) -> str:
        """Table sorted descending by quality: variable | mean | std | quality | rank."""
        sorted_items = sorted(
            self.results.items(),
            key=lambda kv: kv[1].collapse_quality,
            reverse=True,
        )
        lines = [
            "Scaling Variable Specificity",
            f"{'variable':>18}  {'mean(scaled)':>12}  {'std':>7}  {'quality':>8}  rank",
            "-" * 60,
        ]
        for rank, (name, r) in enumerate(sorted_items, 1):
            star = " ★" if rank == 1 else "  "
            mean_s = (
                f"{r.mean_scaled_rho:>12.4f}"
                if math.isfinite(r.mean_scaled_rho)
                else f"{'---':>12}"
            )
            std_s = (
                f"{r.std_scaled_rho:>7.4f}"
                if math.isfinite(r.std_scaled_rho)
                else f"{'---':>7}"
            )
            lines.append(
                f"{name:>18}  {mean_s}  {std_s}  {r.collapse_quality:>8.4f}  #{rank}{star}"
            )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Scaling candidate functions: f(kT, rho_crit, K_eff) → scaled_rho
# ---------------------------------------------------------------------------

_SCALING_CANDIDATES: dict[str, Callable[[float, float, float], float]] = {
    "ρ·√(kT/K_eff)": lambda kT, r, K: r * math.sqrt(kT / K) if K > 1e-9 else math.nan,
    "ρ·√kT":         lambda kT, r, K: r * math.sqrt(kT),
    "ρ/√kT":         lambda kT, r, K: r / math.sqrt(kT) if kT > 0 else math.nan,
    "ρ·kT":          lambda kT, r, K: r * kT,
    "ρ/kT":          lambda kT, r, K: r / kT if kT > 0 else math.nan,
}


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _build_collapse_result(points: list[CollapsePoint]) -> CollapseResult:
    """Compute mean/std/quality from CollapsePoints with scaled_rho already set."""
    valid_sr = np.array(
        [p.scaled_rho for p in points if math.isfinite(p.scaled_rho)], dtype=float
    )
    if len(valid_sr) == 0:
        return CollapseResult(
            points=points, mean_scaled_rho=float("nan"),
            std_scaled_rho=float("nan"), collapse_quality=0.0,
        )

    mean_sr = float(valid_sr.mean())
    std_sr = float(valid_sr.std())
    quality = 1.0 - std_sr / mean_sr if mean_sr > 1e-9 else 0.0

    annotated = [
        CollapsePoint(
            kT=p.kT, rho_crit=p.rho_crit, L_crit=p.L_crit,
            K_eff=p.K_eff, L_th=p.L_th, scaled_rho=p.scaled_rho,
            residual=abs(p.scaled_rho - mean_sr) if math.isfinite(p.scaled_rho) else None,
        )
        for p in points
    ]
    return CollapseResult(
        points=annotated, mean_scaled_rho=mean_sr,
        std_scaled_rho=std_sr, collapse_quality=quality,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def mean_coupling_from_trace(
    trace: PhysicsTrace,
    n_agents: int,
    M_total: float,
    tail_fraction: float = 0.5,
) -> float:
    """Estimate mean pairwise attractive coupling K_eff from the NESS tail.

    Uses the tail of PhysicsTrace.mass_variance (Var(mass) per step) and:

        K_eff = M / N²  -  <Var(m)>_ness / (M * (N-1))

    Falls back to the uniform-mass estimate M/N² when the trace is empty.
    """
    mv = np.array(trace.mass_variance, dtype=float)
    if len(mv) == 0:
        return M_total / (n_agents ** 2)
    start = int(len(mv) * (1.0 - tail_fraction))
    tail = mv[start:] if start < len(mv) else mv
    mean_mv = float(tail.mean())
    return M_total / n_agents ** 2 - mean_mv / (M_total * max(n_agents - 1, 1))


def find_critical_density(
    lambda_array: np.ndarray,
    density_array: np.ndarray,
) -> tuple[float, float] | None:
    """Locate the transition: density at the most negative dλ/dρ (steepest drop).

    Returns (rho_crit, lambda_at_crit) or None if fewer than 3 finite values.
    Non-uniform density spacing is handled via np.gradient(lam, rho).
    """
    lam = np.asarray(lambda_array, dtype=float)
    rho = np.asarray(density_array, dtype=float)

    if np.isfinite(lam).sum() < 3:
        return None

    dlam = np.gradient(lam, rho)
    dlam[~np.isfinite(dlam)] = 0.0

    idx = int(np.argmin(dlam))
    if not np.isfinite(lam[idx]):
        return None
    return float(rho[idx]), float(lam[idx])


def compute_collapse(
    raw: list[tuple[float, float, float]],
    n_agents: int,
) -> CollapseResult:
    """Build CollapseResult from (kT, rho_crit, K_eff) triples.

    Computes scaled_rho = rho_crit * sqrt(kT / K_eff) for each point and
    measures collapse quality as 1 - std(scaled_rho) / mean(scaled_rho).
    A quality above ~0.85 supports the thermal scaling hypothesis.
    """
    points: list[CollapsePoint] = []

    for kT, rho_crit, K_eff in raw:
        L_crit = float(n_agents) / rho_crit
        L_th = math.sqrt(kT / K_eff) if K_eff > 1e-9 else float("nan")
        scaled_rho = rho_crit * L_th if math.isfinite(L_th) else float("nan")
        points.append(CollapsePoint(
            kT=kT, rho_crit=rho_crit, L_crit=L_crit,
            K_eff=K_eff, L_th=L_th, scaled_rho=scaled_rho, residual=None,
        ))

    return _build_collapse_result(points)


def alternative_scalings(
    kT_values: list[float],
    rho_crits: list[float],
    K_eff_values: list[float],
    n_agents: int,
) -> CollapseSpecificity:
    """Evaluate collapse quality for five scaling variable candidates.

    Tests whether ρ·√(kT/K_eff) specifically outperforms simpler alternatives.
    All inputs must be the same length and correspond to the same kT values.

    Candidates:
      ρ·√(kT/K_eff)  — correct hypothesis
      ρ·√kT           — ignores K_eff (if quality matches, K_eff doesn't matter)
      ρ/√kT           — wrong sign in exponent
      ρ·kT            — wrong exponent (linear)
      ρ/kT            — completely wrong

    Note: when K_eff is uniform across kT, ρ·√kT and ρ·√(kT/K_eff) score equally
    (the K_eff factor is a constant multiplier). The distinction only matters when
    K_eff varies with kT (i.e., when mass redistribution is kT-dependent).
    """
    results: dict[str, CollapseResult] = {}

    for name, fn in _SCALING_CANDIDATES.items():
        pts: list[CollapsePoint] = []
        for kT, rho_crit, K_eff in zip(kT_values, rho_crits, K_eff_values):
            L_crit = float(n_agents) / rho_crit
            scaled_rho = fn(kT, rho_crit, K_eff)
            # L_th = the multiplier applied: scaled_rho / rho_crit
            L_th = (
                scaled_rho / rho_crit
                if math.isfinite(scaled_rho) and rho_crit > 0
                else float("nan")
            )
            pts.append(CollapsePoint(
                kT=kT, rho_crit=rho_crit, L_crit=L_crit,
                K_eff=K_eff, L_th=L_th, scaled_rho=scaled_rho, residual=None,
            ))
        results[name] = _build_collapse_result(pts)

    return CollapseSpecificity(results=results)


__all__ = [
    "CollapsePoint",
    "CollapseResult",
    "CollapseSpecificity",
    "mean_coupling_from_trace",
    "find_critical_density",
    "compute_collapse",
    "alternative_scalings",
]

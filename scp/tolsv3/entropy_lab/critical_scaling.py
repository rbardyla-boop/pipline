"""
critical_scaling — Binder cumulant sweep and FSS crossing analysis (Part XV).

Locates T_c from U_4(kT) curve crossings for different N at fixed density.
Also measures susceptibility peaks and supports data collapse rescaling.

Binder crossing property:
  U_4^{N1}(T_c) == U_4^{N2}(T_c)  for all N1, N2 (independent of N at criticality)
  This gives T_c without prior knowledge of T_c.

Susceptibility peak:
  chi = N * Var(x_mean) peaks at the pseudo-critical temperature kT*(N).
  kT*(N) → T_c as N → ∞.

Data collapse:
  x_i = (kT_i - T_c) * N^{1/ν}
  y_i = chi_i * N^{-γ/ν}
  Curves from all N values collapse onto a master scaling function near T_c.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from .lyapunov import estimate_lyapunov
from .observables import PhysicsTrace
from .scaling_observables import (
    binder_cumulant,
    binder_phi_cumulant,
    susceptibility_from_phi_trace,
    susceptibility_from_trace,
)
from .thermodynamic_limit import DensityPreservingSandbox


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BinderPoint:
    kT: float
    u4: float           # binder_cumulant.u4 from x_mean time series
    chi: float          # N * Var(x_mean)
    ep_per_agent: float # report.entropy_production_rate / n_agents
    lambda_max: float   # estimate_lyapunov (open-BC approximation)
    phase: str          # PhaseState.name or "ERROR"
    error: str | None


@dataclass(frozen=True)
class BinderSweep:
    n_agents: int
    density: float
    kT_values: list[float]
    points: list[BinderPoint]
    gamma: float
    n_steps: int

    def u4_array(self) -> np.ndarray:
        return np.array([p.u4 for p in self.points], dtype=float)

    def chi_array(self) -> np.ndarray:
        return np.array([p.chi for p in self.points], dtype=float)

    def kT_array(self) -> np.ndarray:
        return np.array(self.kT_values, dtype=float)


@dataclass(frozen=True)
class CrossingEstimate:
    kT_c: float                   # median crossing temperature across all N pairs
    u4_c: float                   # U_4 at crossing (median across pairs)
    kT_lo: float                  # minimum crossing across pairs (lower bracket)
    kT_hi: float                  # maximum crossing across pairs (upper bracket)
    n_crossing: tuple[int, int]   # N_a, N_b pair closest to median kT_c
    method: str                   # "pairwise_linear"


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def binder_sweep(
    n_agents: int,
    kT_values: Sequence[float],
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
    tail_fraction: float = 0.5,
    lyapunov_steps: int = 150,
) -> BinderSweep:
    """Run a kT sweep for a single N; measure U_4, chi, ep/N, lambda_max.

    Parameters
    ----------
    n_agents:
        System size N. Use N ≤ 26 with density=16.67, k_conf=0 to stay in the
        all-attractive PBC regime (L/2 < 0.8 → no repulsive pairs, stable).
    kT_values:
        Sequence of temperatures to sweep. Log-spaced recommended:
        np.geomspace(0.05, 2.5, 20).
    lyapunov_steps:
        Steps for Benettin Lyapunov estimate. Uses open-BC coupling internally —
        exact for N ≤ 20 at density=16.67 since all pairs are within 0.6 < 0.8.

    Returns
    -------
    BinderSweep with one BinderPoint per kT. Error points have u4=chi=nan.
    """
    points: list[BinderPoint] = []

    for kT in kT_values:
        try:
            with np.errstate(over="raise", invalid="raise"):
                sb = DensityPreservingSandbox(
                    n_agents=n_agents,
                    density=density,
                    kT_global=kT,
                    gamma=gamma,
                    entropy_budget=float(budget_per_agent * n_agents),
                    seed=seed,
                    m_per_agent=m_per_agent,
                    k_conf=k_conf,
                    ness_window=ness_window,
                )
                report, trace = sb.simulate_full(n_steps, concept_force)
                u4 = binder_cumulant(trace, tail_fraction).u4
                chi = susceptibility_from_trace(trace, n_agents, tail_fraction)
                ep = report.entropy_production_rate / n_agents
                phase = report.phase_state.name

                # Lyapunov: fresh same-seed sandbox to avoid post-simulate state
                sb_lya = DensityPreservingSandbox(
                    n_agents=n_agents,
                    density=density,
                    kT_global=kT,
                    gamma=gamma,
                    entropy_budget=float(budget_per_agent * n_agents),
                    seed=seed,
                    m_per_agent=m_per_agent,
                    k_conf=k_conf,
                    ness_window=ness_window,
                )
                lya = estimate_lyapunov(
                    sb_lya, n_steps=lyapunov_steps, concept_force=concept_force
                )
                lambda_max = lya.max_lyapunov

            points.append(BinderPoint(
                kT=kT, u4=u4, chi=chi, ep_per_agent=ep,
                lambda_max=lambda_max, phase=phase, error=None,
            ))
        except Exception as exc:
            points.append(BinderPoint(
                kT=kT, u4=float("nan"), chi=float("nan"),
                ep_per_agent=float("nan"), lambda_max=float("nan"),
                phase="ERROR", error=str(exc)[:80],
            ))

    return BinderSweep(
        n_agents=n_agents,
        density=density,
        kT_values=list(kT_values),
        points=points,
        gamma=gamma,
        n_steps=n_steps,
    )


def find_crossing(sweeps: list[BinderSweep]) -> CrossingEstimate | None:
    """Find T_c from pairwise U_4 curve crossings via linear interpolation.

    For each ordered pair (N_a < N_b): scan adjacent kT intervals where
    U_4_a − U_4_b changes sign. Linear-interpolate within each bracketing
    interval to estimate kT_cross. Return the median and [min, max] bracket
    across all pairs. Return None if no crossing is found in the kT range.

    NaN points (RUNAWAY / ERROR) are skipped; an interval touching a NaN
    endpoint is excluded from the search.
    """
    crossings: list[tuple[float, float, int, int]] = []  # (kT_c, u4_c, n_a, n_b)

    for i, s_a in enumerate(sweeps):
        for s_b in sweeps[i + 1:]:
            if s_a.n_agents >= s_b.n_agents:
                s_a, s_b = s_b, s_a
            u4_a = s_a.u4_array()
            u4_b = s_b.u4_array()
            kT = s_a.kT_array()
            diff = u4_a - u4_b
            for j in range(len(kT) - 1):
                if np.isnan(diff[j]) or np.isnan(diff[j + 1]):
                    continue
                if diff[j] * diff[j + 1] < 0:
                    frac = -diff[j] / (diff[j + 1] - diff[j])
                    kT_cross = float(kT[j] + frac * (kT[j + 1] - kT[j]))
                    u4_cross = float(u4_a[j] + frac * (u4_a[j + 1] - u4_a[j]))
                    crossings.append((kT_cross, u4_cross, s_a.n_agents, s_b.n_agents))

    if not crossings:
        return None

    kT_crosses = [c[0] for c in crossings]
    kT_c = float(np.median(kT_crosses))
    u4_c = float(np.median([c[1] for c in crossings]))
    closest = min(crossings, key=lambda c: abs(c[0] - kT_c))

    return CrossingEstimate(
        kT_c=kT_c,
        u4_c=u4_c,
        kT_lo=float(np.min(kT_crosses)),
        kT_hi=float(np.max(kT_crosses)),
        n_crossing=(closest[2], closest[3]),
        method="pairwise_linear",
    )


def susceptibility_peak(sweep: BinderSweep) -> tuple[float, float]:
    """Return (kT_peak, chi_peak) where chi is maximized.

    Returns (nan, nan) if all points are errors or chi is non-finite everywhere.
    """
    chi = sweep.chi_array()
    kT = sweep.kT_array()
    valid = np.isfinite(chi)
    if not valid.any():
        return (float("nan"), float("nan"))
    valid_kT = kT[valid]
    valid_chi = chi[valid]
    idx = int(np.argmax(valid_chi))
    return (float(valid_kT[idx]), float(valid_chi[idx]))


def collapse_data(
    sweeps: list[BinderSweep],
    kT_c: float,
    gamma_over_nu: float,
    one_over_nu: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Rescale chi data for FSS data collapse.

    Parameters
    ----------
    sweeps:
        List of BinderSweep objects (one per N).
    kT_c:
        Critical temperature estimate (e.g. from find_crossing).
    gamma_over_nu:
        Ratio γ/ν controlling chi rescaling: y = chi * N^{-γ/ν}.
    one_over_nu:
        Inverse correlation-length exponent: x = (kT - T_c) * N^{1/ν}.

    Returns
    -------
    (x_scaled, y_scaled, n_labels) — flat numpy arrays from all N values
    concatenated. NaN chi points are excluded.
    """
    xs: list[np.ndarray] = []
    ys: list[np.ndarray] = []
    ns: list[np.ndarray] = []

    for sweep in sweeps:
        n = sweep.n_agents
        chi = sweep.chi_array()
        kT = sweep.kT_array()
        valid = np.isfinite(chi)
        xs.append((kT[valid] - kT_c) * float(n) ** one_over_nu)
        ys.append(chi[valid] * float(n) ** (-gamma_over_nu))
        ns.append(np.full(int(valid.sum()), n, dtype=int))

    return (np.concatenate(xs), np.concatenate(ys), np.concatenate(ns))


# ---------------------------------------------------------------------------
# Lyapunov sweep
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LyapunovPoint:
    kT: float
    lambda_max: float   # nan if error
    converged: bool
    phase: str          # PhaseState.name or "ERROR"
    error: str | None


@dataclass(frozen=True)
class LyapunovSweep:
    n_agents: int
    density: float
    kT_values: list[float]
    points: list[LyapunovPoint]
    gamma: float
    n_steps: int        # Lyapunov steps (not sim warm-up steps)

    def lambda_array(self) -> np.ndarray:
        return np.array([p.lambda_max for p in self.points], dtype=float)

    def chaos_boundary(self) -> float | None:
        """kT where lambda_max crosses 0 by linear interpolation.

        Returns None if no zero-crossing found (all positive or all negative).
        """
        lam = self.lambda_array()
        kT = np.array(self.kT_values)
        for j in range(len(kT) - 1):
            if np.isnan(lam[j]) or np.isnan(lam[j + 1]):
                continue
            if lam[j] * lam[j + 1] <= 0:
                frac = -lam[j] / (lam[j + 1] - lam[j])
                return float(kT[j] + frac * (kT[j + 1] - kT[j]))
        return None


def lyapunov_sweep(
    n_agents: int,
    kT_values: Sequence[float],
    *,
    density: float = 16.67,
    gamma: float = 0.1,
    m_per_agent: float = 8.0,
    budget_per_agent: float = 2.0,
    n_steps: int = 300,
    concept_force: float = 0.3,
    seed: int = 0,
    k_conf: float = 0.0,
    ness_window: int = 30,
    renorm_every: int = 20,
) -> LyapunovSweep:
    """Measure lambda_max at each kT for a single N.

    Warms up a sandbox with simulate(200) to reach near steady state, then
    runs estimate_lyapunov() on a fresh same-seed sandbox.
    Open-BC coupling approximation; exact for N<=20 at density=16.67.
    """
    points: list[LyapunovPoint] = []

    for kT in kT_values:
        try:
            with np.errstate(over="raise", invalid="raise"):
                sb_warm = DensityPreservingSandbox(
                    n_agents=n_agents,
                    density=density,
                    kT_global=kT,
                    gamma=gamma,
                    entropy_budget=float(budget_per_agent * n_agents),
                    seed=seed,
                    m_per_agent=m_per_agent,
                    k_conf=k_conf,
                    ness_window=ness_window,
                )
                report = sb_warm.simulate(200, concept_force)
                phase = report.phase_state.name

                sb_lya = DensityPreservingSandbox(
                    n_agents=n_agents,
                    density=density,
                    kT_global=kT,
                    gamma=gamma,
                    entropy_budget=float(budget_per_agent * n_agents),
                    seed=seed,
                    m_per_agent=m_per_agent,
                    k_conf=k_conf,
                    ness_window=ness_window,
                )
                lya = estimate_lyapunov(
                    sb_lya,
                    n_steps=n_steps,
                    concept_force=concept_force,
                    renorm_every=renorm_every,
                )

            points.append(LyapunovPoint(
                kT=kT,
                lambda_max=lya.max_lyapunov,
                converged=lya.converged,
                phase=phase,
                error=None,
            ))
        except Exception as exc:
            points.append(LyapunovPoint(
                kT=kT,
                lambda_max=float("nan"),
                converged=False,
                phase="ERROR",
                error=str(exc)[:80],
            ))

    return LyapunovSweep(
        n_agents=n_agents,
        density=density,
        kT_values=list(kT_values),
        points=points,
        gamma=gamma,
        n_steps=n_steps,
    )


def phi_binder_sweep(
    n_agents: int,
    kT_values: Sequence[float],
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
    tail_fraction: float = 0.5,
) -> BinderSweep:
    """Binder sweep using phi=(M_right-M_left)/M_total as the order parameter.

    phi has genuine Z_2 symmetry (phi -> -phi under x -> -x).
    Uses simulate_full() which records phi_series in PhysicsTrace.
    Returns a BinderSweep with u4=U_4(phi) and chi=N*Var(phi).
    lambda_max is set to nan (use lyapunov_sweep separately).
    """
    points: list[BinderPoint] = []

    for kT in kT_values:
        try:
            with np.errstate(over="raise", invalid="raise"):
                sb = DensityPreservingSandbox(
                    n_agents=n_agents,
                    density=density,
                    kT_global=kT,
                    gamma=gamma,
                    entropy_budget=float(budget_per_agent * n_agents),
                    seed=seed,
                    m_per_agent=m_per_agent,
                    k_conf=k_conf,
                    ness_window=ness_window,
                )
                report, trace = sb.simulate_full(n_steps, concept_force)
                binder_r = binder_phi_cumulant(trace, tail_fraction)
                chi = susceptibility_from_phi_trace(trace, n_agents, tail_fraction)
                ep = report.entropy_production_rate / n_agents
                phase = report.phase_state.name

            points.append(BinderPoint(
                kT=kT,
                u4=binder_r.u4,
                chi=chi,
                ep_per_agent=ep,
                lambda_max=float("nan"),
                phase=phase,
                error=None,
            ))
        except Exception as exc:
            points.append(BinderPoint(
                kT=kT,
                u4=float("nan"),
                chi=float("nan"),
                ep_per_agent=float("nan"),
                lambda_max=float("nan"),
                phase="ERROR",
                error=str(exc)[:80],
            ))

    return BinderSweep(
        n_agents=n_agents,
        density=density,
        kT_values=list(kT_values),
        points=points,
        gamma=gamma,
        n_steps=n_steps,
    )


__all__ = [
    "BinderPoint",
    "BinderSweep",
    "CrossingEstimate",
    "LyapunovPoint",
    "LyapunovSweep",
    "binder_sweep",
    "find_crossing",
    "lyapunov_sweep",
    "phi_binder_sweep",
    "susceptibility_peak",
    "collapse_data",
]

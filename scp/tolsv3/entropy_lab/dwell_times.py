"""
dwell_times — Phi zero-crossing analysis for metastability characterization (Part XVII).

Residence-time statistics from phi_series sign changes distinguish:
  exponential  — simple barrier diffusion (Kramers rate, tau ~ exp(dE/kT))
  power law    — glassy / scale-free trapping
  bimodal      — competing attractors with asymmetric stability

Model selection is via goodness-of-fit on log-scale: both exponential and
power-law are fit to the empirical dwell-time histogram, and the better
log-R^2 wins.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class DwellStats:
    n_crossings: int              # number of phi sign flips
    dwell_times: list[int]        # lengths of each residence segment (steps)
    mean_dwell: float             # arithmetic mean residence time
    median_dwell: float           # median residence time
    fit_type: str                 # "exponential" | "power_law" | "insufficient_data"
    fit_params: tuple[float, ...] # (lambda,) for exp; (alpha,) for power law
    fit_r2: float | None          # log-scale R^2 of winning fit


def extract_dwell_times(phi_series: list[float]) -> list[int]:
    """Return residence durations between phi sign changes.

    Each returned integer is the number of consecutive steps spent with the
    same sign of phi. Zero values inherit the sign of the last non-zero sample
    (forward-fill). Returns [len(phi)] when no crossing occurs.
    """
    phi = np.asarray(phi_series, dtype=float)
    n = len(phi)
    if n < 2:
        return [n] if n else []

    signs = np.sign(phi)
    for i in range(1, n):
        if signs[i] == 0.0:
            signs[i] = signs[i - 1]
    if signs[0] == 0.0:
        signs[0] = 1.0

    changes = np.flatnonzero(np.diff(signs)) + 1
    edges = np.concatenate([[0], changes, [n]])
    return [int(edges[k + 1] - edges[k]) for k in range(len(edges) - 1)]


def fit_dwell_distribution(dwell_times: list[int]) -> DwellStats:
    """Fit exponential and power-law models to the dwell-time distribution.

    Exponential: MLE estimator lambda = 1 / mean_dwell.
    Power law:   OLS slope on log-log histogram.

    Both fits are evaluated on the same log-scale R^2; the better fit is
    returned. Returns fit_type="insufficient_data" when fewer than 5 dwells
    are available.
    """
    dt = np.asarray(dwell_times, dtype=float)
    n = len(dt)
    n_crossings = max(0, n - 1)
    mean_dwell = float(np.mean(dt)) if n > 0 else float("nan")
    median_dwell = float(np.median(dt)) if n > 0 else float("nan")

    if n < 5:
        return DwellStats(
            n_crossings=n_crossings,
            dwell_times=list(dwell_times),
            mean_dwell=mean_dwell,
            median_dwell=median_dwell,
            fit_type="insufficient_data",
            fit_params=(),
            fit_r2=None,
        )

    n_bins = min(20, n // 2)
    counts, edges = np.histogram(dt, bins=n_bins, density=True)
    centers = 0.5 * (edges[:-1] + edges[1:])

    def _log_r2(log_obs: np.ndarray, log_pred: np.ndarray) -> float:
        ss_res = float(np.sum((log_obs - log_pred) ** 2))
        ss_tot = float(np.sum((log_obs - log_obs.mean()) ** 2))
        return 1.0 - ss_res / ss_tot if ss_tot > 1e-12 else 0.0

    # --- Exponential (MLE) ---
    lam = 1.0 / mean_dwell if mean_dwell > 0 else float("nan")
    valid_e = counts > 0
    r2_exp = -float("inf")
    if valid_e.sum() >= 3 and not np.isnan(lam):
        log_obs = np.log(counts[valid_e])
        log_pred = np.log(lam) - lam * centers[valid_e]
        r2_exp = _log_r2(log_obs, log_pred)

    # --- Power law (OLS log-log) ---
    valid_p = (counts > 0) & (centers > 0)
    alpha = float("nan")
    r2_pl = -float("inf")
    if valid_p.sum() >= 3:
        log_x = np.log(centers[valid_p])
        log_y = np.log(counts[valid_p])
        slope, intercept = np.polyfit(log_x, log_y, 1)
        alpha = -slope
        r2_pl = _log_r2(log_y, intercept + slope * log_x)

    if not np.isnan(alpha) and r2_pl > r2_exp:
        return DwellStats(
            n_crossings=n_crossings,
            dwell_times=list(dwell_times),
            mean_dwell=mean_dwell,
            median_dwell=median_dwell,
            fit_type="power_law",
            fit_params=(alpha,),
            fit_r2=r2_pl,
        )

    return DwellStats(
        n_crossings=n_crossings,
        dwell_times=list(dwell_times),
        mean_dwell=mean_dwell,
        median_dwell=median_dwell,
        fit_type="exponential",
        fit_params=(lam,) if not np.isnan(lam) else (),
        fit_r2=r2_exp if r2_exp > -float("inf") else None,
    )


__all__ = ["DwellStats", "extract_dwell_times", "fit_dwell_distribution"]

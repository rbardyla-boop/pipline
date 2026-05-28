"""
correlations — Pair correlation G(r) and correlation length ξ.

Key design decisions:
  - PhysicsTrace stores only x_mean, not per-agent positions.  sample_positions()
    re-runs the deterministic integration loop, saves manifold.x snapshots, then
    restores the sandbox's full state (rng + manifold) so the sandbox is
    unchanged on return.
  - 1D normalisation: ideal-gas pair-distance density is the triangular
    distribution p(r) = 2(L−r)/L² where L = max(x) − min(x) pooled over all
    snapshots.  Without this correction G(r) decays to zero at large r.
  - scipy.optimize.curve_fit is optional; a log-linear OLS fallback is used
    when it is unavailable or fails.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass

import numpy as np

from .lagrangian import compute_coupling_matrix, compute_forces


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PairCorrelation:
    r: np.ndarray
    g: np.ndarray
    n_samples: int
    box: float            # effective system size used for normalisation


@dataclass(frozen=True)
class CorrelationLength:
    xi: float             # correlation length ξ from fit
    amplitude: float
    r2: float             # R² of the fit
    method: str           # "scipy" | "loglinear"


# ---------------------------------------------------------------------------
# sample_positions
# ---------------------------------------------------------------------------

def sample_positions(
    sandbox,
    n_steps: int,
    *,
    sample_every: int = 10,
    burn_in: int = 0,
    concept_force: float = 0.5,
) -> list[np.ndarray]:
    """Re-run the integration loop, recording per-agent positions.

    The sandbox's rng and manifold state are fully restored on return, so
    calling this function twice on the same sandbox yields identical results.
    """
    manifold = sandbox.manifold
    thermostat = sandbox.thermostat
    dt = sandbox.dt
    k_conf = sandbox.k_conf
    M_total = sandbox.M_total
    rng = sandbox.rng

    # --- snapshot state ---
    rng_state = rng.bit_generator.state
    x0 = manifold._x.copy()
    p0 = manifold._p.copy()
    mass0 = manifold._mass.copy()
    env0 = manifold._env_mass

    # --- run loop ---
    coupling = compute_coupling_matrix(manifold.mass, manifold.x, M_total)
    snapshots: list[np.ndarray] = []

    try:
        for step in range(burn_in + n_steps):
            x = manifold.x
            p = manifold.p
            mass = manifold.mass

            F = compute_forces(x, coupling, k_conf) + concept_force * np.sin(x)
            p = p + F * dt
            p = thermostat.apply(p, mass, coupling, dt, rng)
            x = x + p * dt

            manifold.set_kinematics(x, p)
            manifold.redistribute_mass()

            mass = manifold.mass
            x = manifold.x
            p = manifold.p
            coupling = compute_coupling_matrix(mass, x, M_total)

            if step >= burn_in and (step - burn_in) % sample_every == 0:
                snapshots.append(x.copy())
    finally:
        # --- restore state unconditionally ---
        rng.bit_generator.state = rng_state
        manifold._x = x0
        manifold._p = p0
        manifold._mass = mass0
        manifold._env_mass = env0

    return snapshots


# ---------------------------------------------------------------------------
# pair_correlation
# ---------------------------------------------------------------------------

def pair_correlation(
    snapshots: list[np.ndarray],
    *,
    n_bins: int = 50,
    r_max: float | None = None,
) -> PairCorrelation:
    """Compute G(r) with triangular-density normalisation for 1D systems.

    G(r) ≈ 1 for an uncorrelated (ideal-gas) distribution.
    """
    all_dists: list[float] = []
    L_max = 0.0

    for snap in snapshots:
        if len(snap) < 2:
            continue
        L = float(snap.max() - snap.min())
        if L > L_max:
            L_max = L
        n = len(snap)
        idx = np.triu_indices(n, k=1)
        dists = np.abs(snap[:, None] - snap[None, :])[idx]
        all_dists.extend(dists.tolist())

    if not all_dists:
        empty = np.zeros(n_bins)
        return PairCorrelation(r=empty.copy(), g=empty.copy(), n_samples=len(snapshots), box=0.0)

    all_dists_arr = np.asarray(all_dists, dtype=float)
    L = L_max if L_max > 0.0 else 1.0

    if r_max is None:
        r_max = L

    counts, bin_edges = np.histogram(all_dists_arr, bins=n_bins, range=(0.0, r_max))
    bin_centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])
    delta_r = r_max / n_bins

    total_pairs = len(all_dists_arr)

    g = np.zeros(n_bins)
    for i, (r_c, count) in enumerate(zip(bin_centers, counts)):
        if r_c >= L or count == 0:
            continue
        ref = 2.0 * (L - r_c) / (L ** 2)
        if ref > 0.0:
            g[i] = (count / total_pairs) / (ref * delta_r)

    return PairCorrelation(
        r=bin_centers,
        g=g,
        n_samples=len(snapshots),
        box=L,
    )


# ---------------------------------------------------------------------------
# correlation_length
# ---------------------------------------------------------------------------

def correlation_length(pc: PairCorrelation) -> CorrelationLength:
    """Fit G(r) − 1 = A·exp(−r/ξ) to extract the correlation length ξ.

    Falls back to log-linear OLS when scipy is unavailable or the fit fails.
    """
    r = pc.r
    g_m1 = pc.g - 1.0

    # Use only bins with positive g-1 and inside the box
    mask = (g_m1 > 0.0) & (r < pc.box) & (r > 0.0)

    if not mask.any():
        return CorrelationLength(xi=float("inf"), amplitude=0.0, r2=0.0, method="loglinear")

    r_fit = r[mask]
    y_fit = g_m1[mask]

    # ---- scipy path ---------------------------------------------------------
    try:
        from scipy.optimize import curve_fit

        def _exp(r, A, xi):
            return A * np.exp(-r / xi)

        xi0 = pc.box / 4.0
        A0 = float(y_fit.max())
        popt, _ = curve_fit(_exp, r_fit, y_fit, p0=[A0, xi0], maxfev=8000)
        A, xi = float(popt[0]), float(abs(popt[1]))

        y_pred = _exp(r_fit, *popt)
        ss_res = float(((y_fit - y_pred) ** 2).sum())
        ss_tot = float(((y_fit - float(y_fit.mean())) ** 2).sum())
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0.0 else 0.0

        return CorrelationLength(xi=xi, amplitude=A, r2=r2, method="scipy")

    except Exception:
        pass

    # ---- log-linear OLS fallback -------------------------------------------
    log_y = np.log(y_fit)
    r_m = float(r_fit.mean())
    log_y_m = float(log_y.mean())

    denom = float(((r_fit - r_m) ** 2).sum())
    if denom == 0.0:
        return CorrelationLength(xi=float("inf"), amplitude=0.0, r2=0.0, method="loglinear")

    slope = float(((r_fit - r_m) * (log_y - log_y_m)).sum()) / denom
    intercept = log_y_m - slope * r_m

    xi = float(-1.0 / slope) if slope < 0.0 else float("inf")
    A = float(np.exp(intercept))

    y_pred = intercept + slope * r_fit
    ss_res = float(((log_y - y_pred) ** 2).sum())
    ss_tot = float(((log_y - log_y_m) ** 2).sum())
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0.0 else 0.0

    return CorrelationLength(xi=xi, amplitude=A, r2=r2, method="loglinear")

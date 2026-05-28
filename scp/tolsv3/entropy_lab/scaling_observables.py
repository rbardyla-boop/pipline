"""
scaling_observables — Binder cumulant and susceptibility from PhysicsTrace (Part XIV).

Both observables are computed from the x_mean time series already recorded by
PhysicsTrace.record(), so no additional simulation runs are required.

Binder cumulant:
  U_4 = 1 - <m^4> / (3 <m^2>^2)
  where m_t = x_mean_t (mean position per step).
  Gaussian fluctuations (disordered)  -> U_4 near 0.
  Bimodal distribution (ordered)      -> U_4 near 2/3.
  U_4 curves for different N cross at T_c (finite-size scaling signature).

Susceptibility (fluctuation-dissipation form):
  chi = N * Var(x_mean)
  Near a critical point: chi ~ N^{gamma/nu} (power-law divergence).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .observables import PhysicsTrace


@dataclass(frozen=True)
class BinderResult:
    u4: float           # 1 - <m^4> / (3 <m^2>^2)
    m2: float           # <m^2>
    m4: float           # <m^4>
    n_steps_used: int   # number of trace steps in the analysis window


def binder_cumulant(
    trace: PhysicsTrace,
    tail_fraction: float = 0.5,
) -> BinderResult:
    """U_4 Binder cumulant from the x_mean time series.

    Parameters
    ----------
    trace:
        PhysicsTrace with at least 4 steps.
    tail_fraction:
        Fraction of the trace to use, counting from the end (default 0.5).
        Skips early transient dynamics.

    Returns
    -------
    BinderResult with u4=0.0 when <m^2> < 1e-12 (degenerate trace).
    """
    m = np.array(trace.x_mean, dtype=float)
    start = int(len(m) * (1.0 - tail_fraction))
    m = m[start:]
    m2 = float(np.mean(m ** 2))
    m4 = float(np.mean(m ** 4))
    u4 = 1.0 - m4 / (3.0 * m2 ** 2) if m2 >= 1e-12 else 0.0
    return BinderResult(u4=u4, m2=m2, m4=m4, n_steps_used=len(m))


def susceptibility_from_trace(
    trace: PhysicsTrace,
    n_agents: int,
    tail_fraction: float = 0.5,
) -> float:
    """chi = N * Var(x_mean) from the fluctuation-dissipation theorem.

    Parameters
    ----------
    trace:
        PhysicsTrace with x_mean recorded per step.
    n_agents:
        System size N; chi scales linearly with N at fixed Var(m).
    tail_fraction:
        Fraction of the trace to use, counting from the end (default 0.5).
    """
    m = np.array(trace.x_mean, dtype=float)
    start = int(len(m) * (1.0 - tail_fraction))
    return float(n_agents * np.var(m[start:]))


def binder_phi_cumulant(
    trace: PhysicsTrace,
    tail_fraction: float = 0.5,
) -> BinderResult:
    """U_4 from phi_series (mass asymmetry order parameter).

    phi = (M_right - M_left) / M_total has Z_2 symmetry: phi -> -phi.
    Low-kT FROZEN cluster: phi ~ +-1 -> U_4 near 2/3.
    High-kT diffuse: phi fluctuates symmetrically -> U_4 near 0.
    Returns BinderResult(u4=0.0, m2=0.0, m4=0.0, n_steps_used=0) if
    phi_series is empty or m2 < 1e-12.
    """
    phi = np.array(trace.phi_series, dtype=float)
    if len(phi) == 0:
        return BinderResult(u4=0.0, m2=0.0, m4=0.0, n_steps_used=0)
    start = int(len(phi) * (1.0 - tail_fraction))
    phi = phi[start:]
    m2 = float(np.mean(phi ** 2))
    m4 = float(np.mean(phi ** 4))
    u4 = 1.0 - m4 / (3.0 * m2 ** 2) if m2 >= 1e-12 else 0.0
    return BinderResult(u4=u4, m2=m2, m4=m4, n_steps_used=len(phi))


def susceptibility_from_phi_trace(
    trace: PhysicsTrace,
    n_agents: int,
    tail_fraction: float = 0.5,
) -> float:
    """chi_phi = N * Var(phi) from the phi_series channel."""
    phi = np.array(trace.phi_series, dtype=float)
    if len(phi) == 0:
        return float("nan")
    start = int(len(phi) * (1.0 - tail_fraction))
    return float(n_agents * np.var(phi[start:]))


__all__ = [
    "BinderResult",
    "binder_cumulant",
    "susceptibility_from_trace",
    "binder_phi_cumulant",
    "susceptibility_from_phi_trace",
]

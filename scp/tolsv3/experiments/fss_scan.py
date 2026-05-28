"""
fss_scan — Finite-size scaling: λ(N), ξ(N), ep/N(N), χ(N).

Uses RenormalizedSandbox so the redistribution channel is intensive by
construction. Three fresh sandboxes are created per N (same seed) to keep
the Lyapunov, correlation, and main simulate measurements comparable.

χ is measured as the finite-difference susceptibility of synchronization_pressure
to the concept force: χ = Δ(sync_pressure) / Δ(concept_force). This is the
linear response of the position-synchronization order parameter to the external
field h. synchronization_pressure = Var(x) / E[x²].

Correlation ξ is sampled from the post-simulate manifold state of the chi_minus
sandbox, capturing the steady-state position structure.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from entropy_lab.correlations import correlation_length, pair_correlation, sample_positions
from entropy_lab.lyapunov import estimate_lyapunov
from entropy_lab.renormalization import RenormalizedSandbox


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FiniteSizePoint:
    n_agents: int
    lambda_max: float       # max Lyapunov exponent (Benettin twin-trajectory)
    xi: float               # correlation length from G(r)
    ep_per_agent: float     # entropy_production_rate / n_agents
    chi: float              # Δ(sync_pressure) / Δ(concept_force)
    phase: str              # PhaseState.name or "ERROR"
    error: str | None


@dataclass(frozen=True)
class FiniteSizeResult:
    n_values: list[int]
    points: list[FiniteSizePoint]
    kT: float
    gamma: float
    m_per_agent: float
    bleed_rate: float
    n_steps: int
    lyapunov_steps: int

    def ascii_table(self) -> str:
        header = (
            f"{'N':>6}  {'ep/N':>10}  {'λ_max':>8}  "
            f"{'ξ':>8}  {'χ':>10}  {'phase':<12}"
        )
        sep = "-" * len(header)
        rows = [header, sep]
        for p in self.points:
            if p.error:
                rows.append(
                    f"{p.n_agents:>6}  {'ERROR':>10}  {'---':>8}  "
                    f"{'---':>8}  {'---':>10}  {p.error[:12]:<12}"
                )
            else:
                xi_str = f"{p.xi:.3f}" if math.isfinite(p.xi) else "inf"
                rows.append(
                    f"{p.n_agents:>6}  {p.ep_per_agent:>10.4f}  "
                    f"{p.lambda_max:>8.4f}  {xi_str:>8}  "
                    f"{p.chi:>10.4f}  {p.phase:<12}"
                )
        return "\n".join(rows)

    def is_intensive(self, rel_tol: float = 0.10) -> bool:
        """True when ep/N spread across N-values is within rel_tol of the mean."""
        valid = [
            p.ep_per_agent
            for p in self.points
            if p.error is None and np.isfinite(p.ep_per_agent)
        ]
        if len(valid) < 2:
            return True
        mean_ep = sum(valid) / len(valid)
        if mean_ep == 0.0:
            return True
        spread = (max(valid) - min(valid)) / abs(mean_ep)
        return spread <= rel_tol


# ---------------------------------------------------------------------------
# Power-law fit utility
# ---------------------------------------------------------------------------

def fit_power_law(
    n_values: list[int],
    obs_values: list[float],
) -> tuple[float, float]:
    """OLS fit log(obs) = alpha * log(N) + log(A). Returns (alpha, A).

    Returns (nan, nan) when fewer than 2 valid (positive, finite) pairs exist.
    """
    pairs = [
        (math.log(n), math.log(v))
        for n, v in zip(n_values, obs_values)
        if n > 0 and v > 0 and math.isfinite(v)
    ]
    if len(pairs) < 2:
        return (float("nan"), float("nan"))

    log_n = np.array([x for x, _ in pairs])
    log_v = np.array([y for _, y in pairs])

    mean_n = float(log_n.mean())
    mean_v = float(log_v.mean())
    var_n = float(((log_n - mean_n) ** 2).sum())
    if var_n == 0.0:
        return (float("nan"), float("nan"))

    alpha = float(((log_n - mean_n) * (log_v - mean_v)).sum() / var_n)
    log_A = mean_v - alpha * mean_n
    return (alpha, math.exp(log_A))


# ---------------------------------------------------------------------------
# Main sweep
# ---------------------------------------------------------------------------

def scan_finite_size(
    n_values: tuple[int, ...] = (10, 20, 50, 100, 200),
    *,
    kT: float = 0.5,
    gamma: float = 0.1,
    m_per_agent: float = 8.0,
    budget_per_agent: float = 2.0,
    bleed_rate: float = 0.02,
    n_steps: int = 600,
    concept_force: float = 0.5,
    seed: int = 0,
    lyapunov_steps: int = 300,
    lyapunov_renorm: int = 20,
    chi_delta: float = 0.1,
) -> FiniteSizeResult:
    """Sweep N values with RenormalizedSandbox; measure λ, ξ, ep/N, χ per N.

    Per N, three fresh sandboxes are created with the same seed:
      1. main sandbox: simulate() → ep_per_agent, phase
      2. lyapunov sandbox: estimate_lyapunov() on _sb → lambda_max
      3a. chi_plus sandbox: simulate(h + chi_delta) → sync_pressure_plus
      3b. chi_minus sandbox: simulate(h - chi_delta) → sync_pressure_minus
         then sample_positions on _sb (post-simulate state) → ξ via G(r)
    """
    points: list[FiniteSizePoint] = []

    for n in n_values:
        base_params: dict = dict(
            n_agents=int(n),
            total_mass=float(m_per_agent * n),
            kT_global=kT,
            gamma=gamma,
            entropy_budget=float(budget_per_agent * n),
            seed=seed,
            x_range=0.3,
            ness_window=20,
            bleed_rate=bleed_rate,
        )
        point = _run_point(
            base_params, n, n_steps, concept_force,
            lyapunov_steps, lyapunov_renorm, chi_delta,
        )
        points.append(point)

    return FiniteSizeResult(
        n_values=list(n_values),
        points=points,
        kT=kT,
        gamma=gamma,
        m_per_agent=m_per_agent,
        bleed_rate=bleed_rate,
        n_steps=n_steps,
        lyapunov_steps=lyapunov_steps,
    )


def _run_point(
    params: dict,
    n: int,
    n_steps: int,
    concept_force: float,
    lyapunov_steps: int,
    lyapunov_renorm: int,
    chi_delta: float,
) -> FiniteSizePoint:
    try:
        with np.errstate(over="raise", invalid="raise"):
            # 1. Main run → ep_per_agent, phase
            sb_main = RenormalizedSandbox(**params)
            report = sb_main.simulate(n_steps=n_steps, concept_force=concept_force)
            ep_per_agent = report.entropy_production_rate / n
            phase = report.phase_state.name

            # 2. Lyapunov (lyapunov.py clones state from _sb and runs its own loop)
            sb_lya = RenormalizedSandbox(**params)
            lya_result = estimate_lyapunov(
                sb_lya._sb,
                n_steps=lyapunov_steps,
                concept_force=concept_force,
                renorm_every=lyapunov_renorm,
            )
            lambda_max = lya_result.max_lyapunov

            # 3. Chi via finite difference on synchronization_pressure
            sb_plus = RenormalizedSandbox(**params)
            report_plus = sb_plus.simulate(
                n_steps=n_steps, concept_force=concept_force + chi_delta
            )

            sb_minus = RenormalizedSandbox(**params)
            report_minus = sb_minus.simulate(
                n_steps=n_steps, concept_force=concept_force - chi_delta
            )
            chi = (
                report_plus.synchronization_pressure
                - report_minus.synchronization_pressure
            ) / (2.0 * chi_delta)

            # 4. Correlation length from post-simulate position structure
            xi = _measure_xi(sb_minus._sb, n_steps, concept_force)

        return FiniteSizePoint(
            n_agents=n,
            lambda_max=lambda_max,
            xi=xi,
            ep_per_agent=ep_per_agent,
            chi=chi,
            phase=phase,
            error=None,
        )
    except Exception as exc:
        return FiniteSizePoint(
            n_agents=n,
            lambda_max=float("nan"),
            xi=float("nan"),
            ep_per_agent=float("nan"),
            chi=float("nan"),
            phase="ERROR",
            error=repr(exc),
        )


def _measure_xi(sb, n_steps: int, concept_force: float) -> float:
    """Sample positions from sb (starting at its current state) and fit G(r)."""
    sample_n = max(n_steps // 2, 50)
    every = max(1, sample_n // 30)
    try:
        snaps = sample_positions(sb, n_steps=sample_n, sample_every=every,
                                 concept_force=concept_force)
        if len(snaps) < 3:
            return float("inf")
        pc = pair_correlation(snaps, n_bins=25)
        cl = correlation_length(pc)
        return cl.xi
    except Exception:
        return float("inf")

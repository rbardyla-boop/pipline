"""
topology_scan — Kernel × N sweep for Part XIII (Localized Interaction Geometry).

Tests whether a locality kernel phi(|x_i - x_j|) applied to the all-to-all
coupling K_ij can restore ep/N intensivity as N grows.

Hypothesis: bounding per-agent interaction density fixes the O(N^2) bandwidth
growth that causes P(slow) to increase with N under all-to-all coupling.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from entropy_lab.lyapunov import estimate_lyapunov
from entropy_lab.topology import (
    AllToAllKernel,
    ExponentialKernel,
    GaussianKernel,
    HardCutoffKernel,
    LocalizedSandbox,
)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TopologyPoint:
    kernel_name: str
    xi_param: float       # characteristic length; inf for AllToAll
    n_agents: int
    ep_per_agent: float
    lambda_max: float
    phase: str
    error: str | None


@dataclass(frozen=True)
class TopologyScan:
    n_values: list[int]
    kernel_configs: list[tuple[str, float]]
    points: list[TopologyPoint]
    kT: float
    gamma: float
    n_steps: int

    def ascii_table(self) -> str:
        lines = [
            f"{'Kernel':<16} {'xi':>6}  {'N':>4}  {'ep/N':>8}  {'λ_max':>8}  phase",
            "-" * 62,
        ]
        for kernel_name, xi_param in self.kernel_configs:
            pts = [
                p for p in self.points
                if p.kernel_name == kernel_name and p.xi_param == xi_param
            ]
            for pt in sorted(pts, key=lambda p: p.n_agents):
                if pt.error:
                    lines.append(
                        f"{pt.kernel_name:<16} {_xi_str(pt.xi_param):>6}  "
                        f"{pt.n_agents:>4}  {'ERROR':>8}  {'':>8}  "
                        f"{pt.error[:20]}"
                    )
                else:
                    lines.append(
                        f"{pt.kernel_name:<16} {_xi_str(pt.xi_param):>6}  "
                        f"{pt.n_agents:>4}  {pt.ep_per_agent:>8.4f}  "
                        f"{pt.lambda_max:>8.4f}  {pt.phase}"
                    )
            intensive = self.is_intensive_at(kernel_name, xi_param)
            ep_vals = [
                p.ep_per_agent for p in pts
                if p.error is None and not math.isnan(p.ep_per_agent)
            ]
            if ep_vals and len(ep_vals) >= 2:
                mean_ep = float(np.mean(ep_vals))
                spread = (max(ep_vals) - min(ep_vals)) / max(abs(mean_ep), 1e-12)
                lines.append(
                    f"  -> is_intensive(0.15): {intensive}  "
                    f"(spread {spread:.1%})"
                )
            lines.append("")
        return "\n".join(lines)

    def is_intensive_at(
        self,
        kernel_name: str,
        xi_param: float,
        rel_tol: float = 0.15,
    ) -> bool:
        """Return True if ep/N spread across N is within rel_tol for this kernel."""
        pts = [
            p for p in self.points
            if p.kernel_name == kernel_name
            and p.xi_param == xi_param
            and p.error is None
            and not math.isnan(p.ep_per_agent)
        ]
        if len(pts) < 2:
            return False
        ep_vals = [p.ep_per_agent for p in pts]
        mean_ep = float(np.mean(ep_vals))
        if mean_ep == 0.0:
            return True
        spread = (max(ep_vals) - min(ep_vals)) / abs(mean_ep)
        return spread <= rel_tol


# ---------------------------------------------------------------------------
# Kernel factory
# ---------------------------------------------------------------------------

_DEFAULT_KERNEL_CONFIGS: list[tuple[str, float]] = [
    ("alltoall", math.inf),
    ("exponential", 1.0),
    ("exponential", 0.3),
    ("exponential", 0.1),
    ("hardcutoff", 0.5),
    ("hardcutoff", 0.2),
]


def _make_kernel(name: str, xi: float):
    if name == "alltoall":
        return AllToAllKernel()
    if name == "exponential":
        return ExponentialKernel(xi=xi)
    if name == "gaussian":
        return GaussianKernel(sigma=xi)
    if name == "hardcutoff":
        return HardCutoffKernel(radius=xi)
    raise ValueError(f"Unknown kernel: {name!r}")


def _xi_str(xi: float) -> str:
    return "inf" if math.isinf(xi) else f"{xi:.2f}"


# ---------------------------------------------------------------------------
# Main sweep
# ---------------------------------------------------------------------------

def scan_topology(
    n_values: tuple[int, ...] = (10, 20, 50),
    kernel_configs: list[tuple[str, float]] | None = None,
    *,
    kT: float = 0.5,
    gamma: float = 0.1,
    m_per_agent: float = 8.0,
    budget_per_agent: float = 2.0,
    n_steps: int = 400,
    concept_force: float = 0.5,
    seed: int = 0,
    x_range: float = 0.3,
    ness_window: int = 20,
    lyapunov_steps: int = 200,
    lyapunov_renorm: int = 20,
) -> TopologyScan:
    """Sweep N × locality kernel and report ep/N intensivity per kernel.

    For each (kernel_config, N):
      1. Run simulate() to get ep_per_agent and phase.
      2. Fresh sandbox with same seed -> estimate_lyapunov().
    Both sandboxes use the localized coupling; Lyapunov inner loop uses
    all-to-all (lagrangian.compute_coupling_matrix) by design — see Part XIII
    notes on deferred Lyapunov-under-locality measurement.

    x_range=0.3 and ness_window=20 match scaling_scan.py (Part XI/XII) so
    the alltoall baseline reproduces known ep/N ≈ 0.26–0.33 results.
    """
    if kernel_configs is None:
        kernel_configs = _DEFAULT_KERNEL_CONFIGS

    points: list[TopologyPoint] = []

    for kernel_name, xi_param in kernel_configs:
        for n in n_values:
            params: dict = dict(
                n_agents=n,
                total_mass=m_per_agent * n,
                kT_global=kT,
                gamma=gamma,
                entropy_budget=budget_per_agent * n,
                seed=seed,
                x_range=x_range,
                ness_window=ness_window,
            )
            kernel = _make_kernel(kernel_name, xi_param)
            try:
                with np.errstate(over="raise", invalid="raise"):
                    sb_main = LocalizedSandbox(**params, kernel=kernel)
                    report = sb_main.simulate(n_steps, concept_force)
                    ep_per_agent = report.entropy_production_rate / n
                    phase = report.phase_state.name

                    sb_lyap = LocalizedSandbox(**params, kernel=kernel)
                    lyap = estimate_lyapunov(
                        sb_lyap,
                        lyapunov_steps,
                        renorm_every=lyapunov_renorm,
                        concept_force=concept_force,
                    )
                    lambda_max = lyap.max_lyapunov

                points.append(TopologyPoint(
                    kernel_name=kernel_name,
                    xi_param=xi_param,
                    n_agents=n,
                    ep_per_agent=ep_per_agent,
                    lambda_max=lambda_max,
                    phase=phase,
                    error=None,
                ))
            except Exception as exc:
                points.append(TopologyPoint(
                    kernel_name=kernel_name,
                    xi_param=xi_param,
                    n_agents=n,
                    ep_per_agent=float("nan"),
                    lambda_max=float("nan"),
                    phase="ERROR",
                    error=str(exc)[:80],
                ))

    return TopologyScan(
        n_values=list(n_values),
        kernel_configs=kernel_configs,
        points=points,
        kT=kT,
        gamma=gamma,
        n_steps=n_steps,
    )

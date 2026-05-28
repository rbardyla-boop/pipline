from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class PhysicsTrace:
    """Mutable record accumulated during a simulation run."""

    steps: list[int] = field(default_factory=list)
    hamiltonian: list[float] = field(default_factory=list)
    entropy_rate: list[float] = field(default_factory=list)
    mass_variance: list[float] = field(default_factory=list)
    x_mean: list[float] = field(default_factory=list)
    env_mass: list[float] = field(default_factory=list)
    phi_series: list[float] = field(default_factory=list)

    def record_phi(self, phi: float) -> None:
        self.phi_series.append(phi)

    def record(
        self,
        step: int,
        H: float,
        ep: float,
        mass_var: float,
        x_m: float,
        env: float,
    ) -> None:
        self.steps.append(step)
        self.hamiltonian.append(H)
        self.entropy_rate.append(ep)
        self.mass_variance.append(mass_var)
        self.x_mean.append(x_m)
        self.env_mass.append(env)

    def __len__(self) -> int:
        return len(self.steps)


# ------------------------------------------------------------------
# Observable 1: Relaxation time
# ------------------------------------------------------------------

def measure_relaxation_time(
    trace: PhysicsTrace,
    perturbation_step: int,
    eps: float = 0.05,
) -> float:
    """Steps for H to return within eps * |H_pre| of its pre-perturbation mean.

    Returns inf if recovery is not achieved within the trace.
    """
    H = np.array(trace.hamiltonian)
    n = len(H)
    if perturbation_step >= n:
        return float("inf")

    H_pre = float(H[:perturbation_step].mean()) if perturbation_step > 0 else float(H[0])
    threshold = eps * abs(H_pre) + 1e-9

    for i in range(perturbation_step, n):
        if abs(H[i] - H_pre) < threshold:
            return float(i - perturbation_step)
    return float("inf")


# ------------------------------------------------------------------
# Observable 2: Synchronization pressure
# ------------------------------------------------------------------

def measure_synchronization_pressure(trace: PhysicsTrace, window: int = 0) -> float:
    """Var(x_mean) / E[x_mean²] — how much the mean position fluctuates.

    High value: agents are not synchronized. Low value: global phase locking.
    window=0 uses the full trace.
    """
    x = np.array(trace.x_mean)
    if window > 0:
        x = x[-window:]
    mean_x2 = float(np.mean(x ** 2)) + 1e-9
    return float(np.var(x)) / mean_x2


# ------------------------------------------------------------------
# Observable 3: Entropy production rate
# ------------------------------------------------------------------

def measure_entropy_production_rate(trace: PhysicsTrace, window: int = 0) -> float:
    """Mean Sigma_dot over the trace or last `window` steps."""
    ep = np.array(trace.entropy_rate)
    if window > 0:
        ep = ep[-window:]
    return float(ep.mean()) if len(ep) > 0 else 0.0


# ------------------------------------------------------------------
# Observable 4: Coordination cost
# ------------------------------------------------------------------

def measure_coordination_cost(trace: PhysicsTrace) -> float:
    """H_late / H_early — ratio of late-phase to early-phase Hamiltonian.

    > 1: energy stored in ordered structure (expensive coordination)
    ≈ 1: flat energy landscape (cheap or no coordination)
    < 1: energy released (structure dissolved)
    """
    H = np.array(trace.hamiltonian)
    n = len(H)
    if n < 4:
        return 1.0
    quarter = max(1, n // 4)
    H_early = float(H[:quarter].mean())
    H_late = float(H[-quarter:].mean())
    if abs(H_early) < 1e-9:
        return 1.0
    return float(abs(H_late / H_early))


# ------------------------------------------------------------------
# Observable 5: Autocorrelation decay time (τ_corr)
# ------------------------------------------------------------------

def measure_autocorrelation_decay_time(trace: PhysicsTrace) -> float:
    """Fit C(τ) = A·exp(-τ/τ_corr) to the x_mean autocorrelation.

    Returns τ_corr in steps, or inf if the fit fails (too-short trace,
    non-positive autocorrelation, or non-decaying signal).
    """
    x = np.array(trace.x_mean, dtype=float)
    n = len(x)
    if n < 10:
        return float("inf")

    x = x - x.mean()
    ac = np.correlate(x, x, mode="full")[n - 1:]   # lags 0, 1, 2, …
    if ac[0] < 1e-12:
        return float("inf")
    ac = ac / ac[0]

    max_lag = n // 2
    ac = ac[:max_lag]
    positive = ac > 1e-6
    if positive.sum() < 3:
        return float("inf")

    lags = np.where(positive)[0].astype(float)
    log_ac = np.log(ac[positive])
    slope, _ = np.polyfit(lags, log_ac, 1)

    if slope >= 0.0:
        return float("inf")
    return float(-1.0 / slope)


# ------------------------------------------------------------------
# Observable 6: Autocorrelation drift (metastability signal)
# ------------------------------------------------------------------

def measure_autocorr_drift(trace: PhysicsTrace, n_windows: int = 4) -> float:
    """OLS slope of τ_corr across n_windows successive trace segments.

    Negative slope → coherence time is shrinking (METASTABLE, not NESS).
    Zero or positive → coherence is stable or growing.
    """
    n = len(trace.x_mean)
    w_size = n // n_windows
    if w_size < 10:
        return 0.0

    tau_values: list[float] = []
    for i in range(n_windows):
        start, end = i * w_size, (i + 1) * w_size
        sub = PhysicsTrace(
            steps=trace.steps[start:end],
            hamiltonian=trace.hamiltonian[start:end],
            entropy_rate=trace.entropy_rate[start:end],
            mass_variance=trace.mass_variance[start:end],
            x_mean=trace.x_mean[start:end],
            env_mass=trace.env_mass[start:end],
        )
        tau = measure_autocorrelation_decay_time(sub)
        tau_values.append(tau if np.isfinite(tau) else 0.0)

    if all(t == 0.0 for t in tau_values):
        return 0.0
    slope, _ = np.polyfit(range(n_windows), tau_values, 1)
    return float(slope)


# ------------------------------------------------------------------
# Observable 7: Collapse threshold (requires external perturbation scan)
# ------------------------------------------------------------------

def measure_collapse_threshold(
    run_fn: "Callable[[float], PhaseState]",
    delta_range: "Sequence[float]",
) -> float:
    """Minimum perturbation magnitude causing an irreversible phase transition.

    run_fn(delta) -> PhaseState for a fresh sandbox seeded with perturbation delta.
    Returns the first delta in delta_range that yields FROZEN or DIFFUSIVE.
    Returns inf if no collapse is found in the range.
    """
    from .phase_transitions import PhaseState

    for delta in sorted(delta_range):
        state = run_fn(float(delta))
        if state in (PhaseState.FROZEN, PhaseState.DIFFUSIVE):
            return float(delta)
    return float("inf")

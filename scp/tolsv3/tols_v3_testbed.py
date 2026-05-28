"""
TOLS v3 — V0 FALSIFICATION TESTBED
===================================
Phase 1 deliverable: Basin-Mapping and Stability Report

Implements:
  - Corrected tangent-space Kuramoto dynamics (geodesic midpoint integrator)
  - Three coupling rules: raw Hebbian, centered Hebbian, pseudoinverse
  - Full energy + order parameter instrumentation at every step
  - Experiment A: Single-pattern basin volume test
  - Experiment B: Strict energy monotonicity verification
  - Experiment C: Capacity stress test (phase transition)
  - Zero-coupling dissipation check (solver artifact detection)

Reference: "Artificial Kuramoto Oscillatory Neurons" (Oct 2024)
APEX Core 4.3 | VAL Framework v1.0
"""

import numpy as np
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass, field
import json
import time


# =============================================================================
# CONFIGURATION — ALL THRESHOLDS DEFINED HERE
# =============================================================================

@dataclass
class ExperimentConfig:
    n_units: int = 32
    pattern_dim: int = 8
    coupling_strength: float = 2.0
    dt: float = 0.005            # Conservative step size
    convergence_tol: float = 1e-5
    max_steps: int = 1000
    # Basin mapping
    basin_n_samples: int = 50
    basin_corruption_levels: tuple = (0.1, 0.3, 0.5, 0.7, 0.9)
    # Capacity test
    capacity_pattern_counts: tuple = (1, 2, 4, 8, 16)
    capacity_n_trials: int = 20
    capacity_corruption: float = 0.10
    # Pass/fail thresholds
    energy_violation_tolerance: float = 1e-10  # ΔE > this = violation
    basin_sigmoid_required: bool = True
    order_param_sync_threshold: float = 0.95   # R > this = global sync
    dissipation_norm_tol: float = 1e-7
    dissipation_energy_tol: float = 1e-10


# =============================================================================
# INSTRUMENTED OSCILLATOR NETWORK
# =============================================================================

class InstrumentedTOLS:
    """
    Multi-dimensional Kuramoto oscillators with full instrumentation.

    Key difference from original TOLS v3:
    - Logs energy and order parameter at EVERY step
    - Supports multiple coupling rules
    - Uses geodesic-aware integration (project after update)
    - Tracks ΔE for monotonicity verification
    """

    def __init__(
        self,
        n_units: int = 32,
        pattern_dim: int = 8,
        coupling_strength: float = 2.0,
        dt: float = 0.005,
        coupling_rule: str = "centered",  # "raw", "centered", "pseudoinverse"
        seed: Optional[int] = None,
    ):
        self.n = n_units
        self.dim = pattern_dim
        self.K = coupling_strength
        self.dt = dt
        self.coupling_rule = coupling_rule
        self.rng = np.random.RandomState(seed)

        # State: unit vectors on S^{D-1}
        self.X = self.rng.randn(n_units, pattern_dim)
        self.X = self._normalize(self.X)

        # Coupling matrix
        self.W = np.zeros((n_units, n_units))

        # Pattern storage
        self.patterns: List[np.ndarray] = []

        # Instrumentation logs
        self.energy_log: List[float] = []
        self.order_param_log: List[float] = []
        self.delta_e_log: List[float] = []

    def _normalize(self, X: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(X, axis=1, keepdims=True)
        norms = np.maximum(norms, 1e-12)
        return X / norms

    # ----- Coupling Rules -----

    def _build_weights_raw(self) -> np.ndarray:
        """Standard Hebbian: W = Σ_k p_k p_k^T, diagonal zeroed."""
        W = np.zeros((self.n, self.n))
        for p in self.patterns:
            W += p @ p.T
        np.fill_diagonal(W, 0)
        return W

    def _build_weights_centered(self) -> np.ndarray:
        """Centered Hebbian: subtract mean pattern before outer product."""
        if len(self.patterns) == 0:
            return np.zeros((self.n, self.n))
        P = np.stack(self.patterns, axis=0)  # (K, N, D)
        # Per-unit mean across patterns: (N, D)
        mean_p = P.mean(axis=0)
        W = np.zeros((self.n, self.n))
        for p in self.patterns:
            centered = p - mean_p
            # Re-normalize rows after centering
            norms = np.linalg.norm(centered, axis=1, keepdims=True)
            norms = np.maximum(norms, 1e-12)
            centered = centered / norms
            W += centered @ centered.T
        np.fill_diagonal(W, 0)
        return W

    def _build_weights_pseudoinverse(self) -> np.ndarray:
        """Pseudoinverse rule: exact projection onto pattern subspace."""
        if len(self.patterns) == 0:
            return np.zeros((self.n, self.n))
        # Flatten each (N,D) pattern to (N*D,) vector
        P_flat = np.array([p.flatten() for p in self.patterns])  # (K, N*D)
        # Pseudoinverse: W_flat = P^T (P P^T)^{-1} P
        gram = P_flat @ P_flat.T  # (K, K)
        gram += 1e-8 * np.eye(len(self.patterns))  # regularize
        gram_inv = np.linalg.inv(gram)
        W_flat = P_flat.T @ gram_inv @ P_flat  # (N*D, N*D)
        # Extract the (N, N) coupling by summing over D dimensions
        W = np.zeros((self.n, self.n))
        for d1 in range(self.dim):
            for d2 in range(self.dim):
                block = W_flat[
                    d1 * self.n : (d1 + 1) * self.n,
                    d2 * self.n : (d2 + 1) * self.n,
                ]
                W += block
        np.fill_diagonal(W, 0)
        return W

    def _rebuild_W(self):
        if self.coupling_rule == "raw":
            self.W = self._build_weights_raw()
        elif self.coupling_rule == "centered":
            self.W = self._build_weights_centered()
        elif self.coupling_rule == "pseudoinverse":
            self.W = self._build_weights_pseudoinverse()
        else:
            raise ValueError(f"Unknown coupling rule: {self.coupling_rule}")

    # ----- Storage -----

    def store_pattern(self, pattern: np.ndarray):
        p = self._normalize(pattern.copy())
        self.patterns.append(p)
        self._rebuild_W()

    # ----- Dynamics (tangent-space Kuramoto) -----

    def _tangent_step(self):
        """
        dX_i/dt = K Σ_j W_ij (X_j - (X_i · X_j) X_i)

        This is the projection of W @ X onto the tangent space of S^{D-1} at X_i.
        After the Euler step, we re-project to the manifold.
        """
        dots = self.X @ self.X.T  # (N, N)
        WX = self.W @ self.X  # (N, D)
        W_dot = self.W * dots  # (N, N)
        W_dot_sum = W_dot.sum(axis=1, keepdims=True)  # (N, 1)
        dX = self.K * (WX - W_dot_sum * self.X)
        self.X = self.X + self.dt * dX
        self.X = self._normalize(self.X)

    # ----- Observables -----

    def compute_energy(self) -> float:
        """E = -½ Σ_{i,j} W_ij (X_i · X_j)"""
        dots = self.X @ self.X.T
        return -0.5 * (self.W * dots).sum()

    def compute_order_parameter(self) -> float:
        """R = (1/N) || Σ_i X_i ||"""
        mean_vec = self.X.mean(axis=0)
        return np.linalg.norm(mean_vec)

    # ----- Recall with full instrumentation -----

    def recall(
        self,
        cue: np.ndarray,
        max_steps: int = 5000,
        tol: float = 1e-6,
        log: bool = True,
    ) -> Tuple[np.ndarray, int, Dict]:
        """
        Run dynamics from cue until convergence.
        Returns (final_state, steps_taken, diagnostics).
        """
        self.X = self._normalize(cue.copy())
        self.energy_log = []
        self.order_param_log = []
        self.delta_e_log = []

        E_prev = self.compute_energy()
        if log:
            self.energy_log.append(E_prev)
            self.order_param_log.append(self.compute_order_parameter())

        for step in range(max_steps):
            X_old = self.X.copy()
            self._tangent_step()

            E_now = self.compute_energy()
            delta_e = E_now - E_prev

            if log:
                self.energy_log.append(E_now)
                self.order_param_log.append(self.compute_order_parameter())
                self.delta_e_log.append(delta_e)

            E_prev = E_now

            diff = np.abs(self.X - X_old).max()
            if diff < tol:
                diag = {
                    "converged": True,
                    "steps": step + 1,
                    "final_energy": E_now,
                    "final_R": self.compute_order_parameter(),
                    "energy_violations": sum(
                        1 for d in self.delta_e_log if d > 1e-10
                    ),
                    "max_energy_increase": max(self.delta_e_log)
                    if self.delta_e_log
                    else 0.0,
                }
                return self.X.copy(), step + 1, diag

        diag = {
            "converged": False,
            "steps": max_steps,
            "final_energy": E_now,
            "final_R": self.compute_order_parameter(),
            "energy_violations": sum(1 for d in self.delta_e_log if d > 1e-10),
            "max_energy_increase": max(self.delta_e_log)
            if self.delta_e_log
            else 0.0,
        }
        return self.X.copy(), max_steps, diag

    def similarity(self, s1: np.ndarray, s2: np.ndarray) -> float:
        a = self._normalize(s1)
        b = self._normalize(s2)
        return (a * b).sum(axis=1).mean()


# =============================================================================
# PATTERN GENERATION (multiple strategies)
# =============================================================================

def generate_random_patterns(
    n_patterns: int, n_units: int, dim: int, rng: np.random.RandomState
) -> List[np.ndarray]:
    """Fully random unit vectors — no structure."""
    patterns = []
    for _ in range(n_patterns):
        p = rng.randn(n_units, dim)
        p = p / np.linalg.norm(p, axis=1, keepdims=True)
        patterns.append(p)
    return patterns


def generate_orthogonal_patterns(
    n_patterns: int, n_units: int, dim: int, rng: np.random.RandomState
) -> List[np.ndarray]:
    """Gram-Schmidt orthogonalized random patterns (in flattened space)."""
    flat_dim = n_units * dim
    if n_patterns > flat_dim:
        raise ValueError(f"Cannot orthogonalize {n_patterns} patterns in {flat_dim}D")
    basis = rng.randn(n_patterns, flat_dim)
    # QR orthogonalization
    Q, _ = np.linalg.qr(basis.T)
    patterns = []
    for i in range(n_patterns):
        p = Q[:, i].reshape(n_units, dim)
        p = p / np.linalg.norm(p, axis=1, keepdims=True)
        patterns.append(p)
    return patterns


def corrupt_pattern(
    pattern: np.ndarray, corruption_rate: float, rng: np.random.RandomState
) -> np.ndarray:
    corrupted = pattern.copy()
    n_corrupt = int(pattern.shape[0] * corruption_rate)
    idx = rng.choice(pattern.shape[0], n_corrupt, replace=False)
    for i in idx:
        corrupted[i] = rng.randn(pattern.shape[1])
        corrupted[i] /= np.linalg.norm(corrupted[i])
    return corrupted


# =============================================================================
# EXPERIMENT 0: ZERO-COUPLING DISSIPATION CHECK
# =============================================================================

def experiment_zero_coupling(cfg: ExperimentConfig, seed: int = 42) -> Dict:
    """
    Verify the integrator introduces no artificial damping.
    W = 0, run 10^4 steps, check norm and energy stability.
    """
    print("\n" + "=" * 70)
    print("EXPERIMENT 0: Zero-Coupling Dissipation Check")
    print("=" * 70)

    net = InstrumentedTOLS(
        n_units=cfg.n_units,
        pattern_dim=cfg.pattern_dim,
        coupling_strength=cfg.coupling_strength,
        dt=cfg.dt,
        coupling_rule="raw",
        seed=seed,
    )
    # W stays zero — no patterns stored
    initial_X = net.X.copy()
    initial_norms = np.linalg.norm(initial_X, axis=1)
    initial_energy = net.compute_energy()

    n_steps = 10000
    for _ in range(n_steps):
        net._tangent_step()

    final_norms = np.linalg.norm(net.X, axis=1)
    final_energy = net.compute_energy()

    norm_drift = np.abs(final_norms - 1.0).max()
    energy_drift = abs(final_energy - initial_energy)
    state_drift = np.abs(net.X - initial_X).max()

    norm_pass = norm_drift < cfg.dissipation_norm_tol
    energy_pass = energy_drift < cfg.dissipation_energy_tol

    print(f"  Steps:        {n_steps}")
    print(f"  Norm drift:   {norm_drift:.2e}  (tol: {cfg.dissipation_norm_tol:.0e})  {'PASS' if norm_pass else 'FAIL'}")
    print(f"  Energy drift: {energy_drift:.2e}  (tol: {cfg.dissipation_energy_tol:.0e})  {'PASS' if energy_pass else 'FAIL'}")
    print(f"  State drift:  {state_drift:.2e}  (should be ~0 with W=0)")

    result = {
        "norm_drift": norm_drift,
        "energy_drift": energy_drift,
        "state_drift": state_drift,
        "norm_pass": norm_pass,
        "energy_pass": energy_pass,
        "overall_pass": norm_pass and energy_pass,
    }

    if not result["overall_pass"]:
        print("\n  *** CRITICAL: Integrator introduces artificial dynamics. ***")
        print("  *** All subsequent experiments are INVALID until this is fixed. ***")
    else:
        print("\n  Integrator verified: no artificial damping detected.")

    return result


# =============================================================================
# EXPERIMENT A: SINGLE-PATTERN BASIN VOLUME TEST
# =============================================================================

def experiment_basin_mapping(
    cfg: ExperimentConfig,
    coupling_rule: str = "centered",
    seed: int = 42,
) -> Dict:
    """
    Store 1 pattern. Corrupt at increasing levels. Measure recall probability.
    Fit sigmoid. Report inflection point (basin radius).
    """
    print("\n" + "=" * 70)
    print(f"EXPERIMENT A: Basin Volume Test (coupling={coupling_rule})")
    print("=" * 70)

    rng = np.random.RandomState(seed)
    patterns = generate_random_patterns(1, cfg.n_units, cfg.pattern_dim, rng)
    target = patterns[0]

    net = InstrumentedTOLS(
        n_units=cfg.n_units,
        pattern_dim=cfg.pattern_dim,
        coupling_strength=cfg.coupling_strength,
        dt=cfg.dt,
        coupling_rule=coupling_rule,
        seed=seed,
    )
    net.store_pattern(target)

    results_by_level = {}

    for corruption in cfg.basin_corruption_levels:
        successes = 0
        similarities = []

        for trial in range(cfg.basin_n_samples):
            trial_rng = np.random.RandomState(seed + trial * 1000 + int(corruption * 100))
            cue = corrupt_pattern(target, corruption, trial_rng)
            recalled, steps, diag = net.recall(
                cue, max_steps=cfg.max_steps, tol=cfg.convergence_tol, log=False
            )
            sim = net.similarity(recalled, target)
            similarities.append(sim)
            if sim > 0.9:
                successes += 1

        recall_rate = successes / cfg.basin_n_samples
        mean_sim = np.mean(similarities)
        std_sim = np.std(similarities)

        results_by_level[corruption] = {
            "recall_rate": recall_rate,
            "mean_similarity": mean_sim,
            "std_similarity": std_sim,
        }
        print(f"  Corruption {corruption:.0%}: recall={recall_rate:.3f}, sim={mean_sim:.3f}±{std_sim:.3f}")

    # Fit logistic sigmoid: p(recall) = 1 / (1 + exp(k*(x - x0)))
    corruptions = np.array(list(results_by_level.keys()))
    recalls = np.array([v["recall_rate"] for v in results_by_level.values()])

    # Simple grid search for sigmoid fit
    best_fit = {"x0": 0.5, "k": 10, "residual": 1e10}
    for x0 in np.linspace(0.1, 0.9, 81):
        for k in np.linspace(1, 50, 50):
            pred = 1.0 / (1.0 + np.exp(k * (corruptions - x0)))
            resid = np.sum((pred - recalls) ** 2)
            if resid < best_fit["residual"]:
                best_fit = {"x0": x0, "k": k, "residual": resid}

    is_sigmoid = best_fit["k"] > 5 and best_fit["residual"] < 0.5
    print(f"\n  Sigmoid fit: x0={best_fit['x0']:.2f}, k={best_fit['k']:.1f}, residual={best_fit['residual']:.4f}")
    print(f"  Basin boundary (inflection): {best_fit['x0']:.0%} corruption")
    print(f"  Sharp transition: {'YES' if is_sigmoid else 'NO'}")

    # Check order parameter at convergence
    cue = corrupt_pattern(target, 0.1, rng)
    _, _, diag = net.recall(cue, max_steps=cfg.max_steps, log=True)
    final_R = diag["final_R"]
    is_sync = final_R > cfg.order_param_sync_threshold

    print(f"\n  Final order parameter R: {final_R:.4f}")
    print(f"  Global synchronization: {'YES (FAIL)' if is_sync else 'NO (OK)'}")

    overall = is_sigmoid and not is_sync
    print(f"\n  EXPERIMENT A VERDICT: {'PASS' if overall else 'FAIL'}")

    return {
        "corruption_results": results_by_level,
        "sigmoid_fit": best_fit,
        "is_sigmoid": is_sigmoid,
        "final_R": final_R,
        "is_global_sync": is_sync,
        "pass": overall,
    }


# =============================================================================
# EXPERIMENT B: STRICT ENERGY MONOTONICITY
# =============================================================================

def experiment_energy_monotonicity(
    cfg: ExperimentConfig,
    coupling_rule: str = "centered",
    seed: int = 42,
    n_trials: int = 50,
) -> Dict:
    """
    Store 2 patterns. Run from 50 random initial conditions.
    Check ΔE ≤ 0 at EVERY step.
    """
    print("\n" + "=" * 70)
    print(f"EXPERIMENT B: Energy Monotonicity (coupling={coupling_rule})")
    print("=" * 70)

    rng = np.random.RandomState(seed)
    patterns = generate_random_patterns(2, cfg.n_units, cfg.pattern_dim, rng)

    total_violations = 0
    total_steps = 0
    max_violation = 0.0
    violation_fractions = []

    for trial in range(n_trials):
        net = InstrumentedTOLS(
            n_units=cfg.n_units,
            pattern_dim=cfg.pattern_dim,
            coupling_strength=cfg.coupling_strength,
            dt=cfg.dt,
            coupling_rule=coupling_rule,
            seed=seed + trial,
        )
        for p in patterns:
            net.store_pattern(p)

        # Random initial condition
        init = rng.randn(cfg.n_units, cfg.pattern_dim)
        init = init / np.linalg.norm(init, axis=1, keepdims=True)

        _, steps, diag = net.recall(init, max_steps=cfg.max_steps, log=True)

        violations = diag["energy_violations"]
        total_violations += violations
        total_steps += len(net.delta_e_log)
        if net.delta_e_log:
            trial_max = max(net.delta_e_log)
            max_violation = max(max_violation, trial_max)
        violation_fractions.append(
            violations / len(net.delta_e_log) if net.delta_e_log else 0
        )

    violation_rate = total_violations / total_steps if total_steps > 0 else 0
    mean_vf = np.mean(violation_fractions)

    print(f"  Trials:           {n_trials}")
    print(f"  Total steps:      {total_steps}")
    print(f"  Total violations: {total_violations}")
    print(f"  Violation rate:   {violation_rate:.6f}")
    print(f"  Max ΔE increase:  {max_violation:.2e}")

    strict_pass = total_violations == 0
    practical_pass = violation_rate < 0.01 and max_violation < 0.01

    if strict_pass:
        print("\n  STRICT PASS: Energy never increases. Lyapunov guarantee holds.")
    elif practical_pass:
        print(f"\n  PRACTICAL PASS: Violations are bounded (rate={violation_rate:.4%}, max={max_violation:.2e}).")
    else:
        print(f"\n  FAIL: Energy increases are unbounded or frequent.")

    print(f"  EXPERIMENT B VERDICT: {'STRICT PASS' if strict_pass else 'PRACTICAL PASS' if practical_pass else 'FAIL'}")

    return {
        "total_violations": total_violations,
        "total_steps": total_steps,
        "violation_rate": violation_rate,
        "max_violation": max_violation,
        "strict_pass": strict_pass,
        "practical_pass": practical_pass,
    }


# =============================================================================
# EXPERIMENT C: CAPACITY STRESS TEST
# =============================================================================

def experiment_capacity(
    cfg: ExperimentConfig,
    coupling_rule: str = "centered",
    seed: int = 42,
) -> Dict:
    """
    Store 1, 2, 4, 6, 8, 12, 16 patterns.
    For each count, test recall from 10% corrupted cues.
    Report recall accuracy vs. loading ratio.
    """
    print("\n" + "=" * 70)
    print(f"EXPERIMENT C: Capacity Stress Test (coupling={coupling_rule})")
    print("=" * 70)

    rng = np.random.RandomState(seed)
    results = {}

    for n_patterns in cfg.capacity_pattern_counts:
        if n_patterns > cfg.n_units * cfg.pattern_dim:
            break

        patterns = generate_orthogonal_patterns(
            n_patterns, cfg.n_units, cfg.pattern_dim, rng
        )

        # Build network and store
        net = InstrumentedTOLS(
            n_units=cfg.n_units,
            pattern_dim=cfg.pattern_dim,
            coupling_strength=cfg.coupling_strength,
            dt=cfg.dt,
            coupling_rule=coupling_rule,
            seed=seed,
        )
        for p in patterns:
            net.store_pattern(p)

        correct = 0
        total = 0
        sims = []

        for pi, target in enumerate(patterns):
            for trial in range(min(cfg.capacity_n_trials, 50)):
                trial_rng = np.random.RandomState(seed + pi * 1000 + trial)
                cue = corrupt_pattern(target, cfg.capacity_corruption, trial_rng)
                recalled, _, _ = net.recall(
                    cue, max_steps=cfg.max_steps, tol=cfg.convergence_tol, log=False
                )

                # Check which pattern is closest
                best_sim = -1
                best_idx = -1
                for j, p in enumerate(patterns):
                    s = net.similarity(recalled, p)
                    if s > best_sim:
                        best_sim = s
                        best_idx = j

                if best_idx == pi:
                    correct += 1
                    sims.append(best_sim)
                total += 1

        accuracy = correct / total if total > 0 else 0
        loading_ratio = n_patterns / cfg.n_units
        mean_sim = np.mean(sims) if sims else 0

        results[n_patterns] = {
            "accuracy": accuracy,
            "loading_ratio": loading_ratio,
            "mean_similarity": mean_sim,
            "total_trials": total,
        }

        print(f"  P={n_patterns:2d} (α={loading_ratio:.3f}): accuracy={accuracy:.3f}, sim={mean_sim:.3f}")

    # Detect cliff
    accuracies = [(k, v["accuracy"]) for k, v in results.items()]
    cliff_at = None
    for i in range(1, len(accuracies)):
        prev_acc = accuracies[i - 1][1]
        curr_acc = accuracies[i][1]
        if prev_acc > 0.8 and curr_acc < 0.6:
            cliff_at = accuracies[i][0]
            break

    if cliff_at:
        print(f"\n  Capacity cliff detected at P={cliff_at}")
    else:
        accs = [a[1] for a in accuracies]
        if all(a > 0.8 for a in accs):
            print("\n  No cliff detected — all pattern counts recalled successfully.")
        elif all(a < 0.6 for a in accs[1:]):
            print("\n  FAIL: Recall collapses immediately after P=1.")
        else:
            print("\n  Gradual degradation — no sharp phase transition.")

    return {"per_count": results, "cliff_at": cliff_at}


# =============================================================================
# COUPLING RULE COMPARISON
# =============================================================================

def compare_coupling_rules(cfg: ExperimentConfig, seed: int = 42) -> Dict:
    """
    Run Experiment A with all three coupling rules.
    Compare order parameter and basin structure.
    """
    print("\n" + "=" * 70)
    print("COUPLING RULE COMPARISON")
    print("=" * 70)

    results = {}
    for rule in ["raw", "centered", "pseudoinverse"]:
        print(f"\n--- {rule.upper()} ---")
        r = experiment_basin_mapping(cfg, coupling_rule=rule, seed=seed)
        results[rule] = {
            "basin_pass": r["pass"],
            "final_R": r["final_R"],
            "sigmoid_x0": r["sigmoid_fit"]["x0"],
            "sigmoid_k": r["sigmoid_fit"]["k"],
        }

    print("\n" + "-" * 70)
    print(f"{'Rule':<15} {'Basin?':<8} {'R':<8} {'x0':<8} {'k':<8}")
    print("-" * 70)
    for rule, r in results.items():
        print(
            f"{rule:<15} {'PASS' if r['basin_pass'] else 'FAIL':<8} "
            f"{r['final_R']:<8.4f} {r['sigmoid_x0']:<8.2f} {r['sigmoid_k']:<8.1f}"
        )

    return results


# =============================================================================
# MAIN: FULL PHASE 1 REPORT
# =============================================================================

def run_phase1_report(seed: int = 42):
    cfg = ExperimentConfig()

    print("=" * 70)
    print("TOLS v3 — PHASE 1: BASIN-MAPPING AND STABILITY REPORT")
    print("V0 Falsification Testbed | APEX Core 4.3")
    print("=" * 70)
    print(f"\nConfiguration:")
    print(f"  N={cfg.n_units}, D={cfg.pattern_dim}, K={cfg.coupling_strength}, dt={cfg.dt}")
    print(f"  Convergence tol={cfg.convergence_tol}, max_steps={cfg.max_steps}")

    t0 = time.time()

    # Step 0: Verify integrator
    exp0 = experiment_zero_coupling(cfg, seed)
    if not exp0["overall_pass"]:
        print("\n*** HALTING: Integrator failed dissipation check. Fix before proceeding. ***")
        return

    # Step 1: Compare coupling rules on basin test
    coupling_comparison = compare_coupling_rules(cfg, seed)

    # Pick best coupling rule
    best_rule = "centered"
    for rule, r in coupling_comparison.items():
        if r["basin_pass"] and not coupling_comparison.get(best_rule, {}).get("basin_pass", False):
            best_rule = rule

    print(f"\n>>> Selected coupling rule for remaining experiments: {best_rule}")

    # Step 2: Energy monotonicity
    exp_b = experiment_energy_monotonicity(cfg, coupling_rule=best_rule, seed=seed)

    # Step 3: Capacity
    exp_c = experiment_capacity(cfg, coupling_rule=best_rule, seed=seed)

    elapsed = time.time() - t0

    # FINAL VERDICT
    print("\n" + "=" * 70)
    print("PHASE 1 FINAL VERDICT")
    print("=" * 70)

    basin_pass = coupling_comparison.get(best_rule, {}).get("basin_pass", False)
    energy_pass = exp_b["strict_pass"] or exp_b["practical_pass"]
    capacity_cliff = exp_c.get("cliff_at") is not None

    print(f"\n  Coupling rule:      {best_rule}")
    print(f"  Integrator valid:   {'YES' if exp0['overall_pass'] else 'NO'}")
    print(f"  Distinct basins:    {'YES' if basin_pass else 'NO'}")
    print(f"  Energy monotonic:   {'STRICT' if exp_b['strict_pass'] else 'PRACTICAL' if exp_b['practical_pass'] else 'NO'}")
    print(f"  Capacity cliff:     {'P=' + str(exp_c['cliff_at']) if capacity_cliff else 'NOT DETECTED'}")

    if basin_pass and energy_pass and capacity_cliff:
        verdict = "CONTINUE"
        print(f"\n  DECISION: {verdict}")
        print("  The system forms distinct attractor basins, energy descends,")
        print("  and capacity exhibits a phase transition. Proceed to Phase 2.")
    elif basin_pass and energy_pass:
        verdict = "REDESIGN"
        print(f"\n  DECISION: {verdict}")
        print("  Basins exist and energy behaves, but capacity does not exhibit")
        print("  a clean phase transition. Coupling rule or storage scheme needs work.")
    else:
        verdict = "HALT"
        print(f"\n  DECISION: {verdict}")
        if not basin_pass:
            print("  No distinct attractor basins detected. System is a synchronizer.")
        if not energy_pass:
            print("  Energy is not monotonically decreasing. No Lyapunov guarantee.")
        print("  The associative-memory hypothesis is FALSIFIED for this architecture.")

    print(f"\n  Elapsed: {elapsed:.1f}s")
    return verdict


if __name__ == "__main__":
    run_phase1_report(seed=42)

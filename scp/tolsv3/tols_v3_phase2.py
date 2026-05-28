"""
TOLS v3 — PHASE 2: REDESIGN
============================
Addresses Phase 1 verdict: shallow basins + blurry reconstruction.

Two targeted fixes:
  1. Tangent-bundle pseudoinverse: coupling W_ij is a D×D matrix, not a scalar.
     Force on unit i = Σ_k alpha_k * p_k^i, where alpha = G^{-1} @ overlaps.
     overlaps_l = <p_l, X>_F = Σ_j p_l^j · X_j  (Frobenius inner product)
     Energy = -½ overlaps^T G^{-1} overlaps = -½ alpha · overlaps.

  2. Adaptive coupling strength K_eff = K * N / P.
     Scales the field strength to compensate pattern interference at load.

Experiments:
  D — Reconstruction fidelity: tensor pseudoinverse vs scalar Hebbian (P=1..8)
  E — K sweep: basin depth as a function of K (single pattern, vary corruption)
  F — Capacity revisited: phase transition with tensor pseudoinverse

All Phase 1 instrumentation is preserved. Energy monotonicity re-verified
for tensor coupling before proceeding.
"""

import numpy as np
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
import time


# =============================================================================
# CONFIG
# =============================================================================

@dataclass
class Phase2Config:
    n_units: int = 32
    pattern_dim: int = 8
    base_K: float = 4.0            # Stronger than Phase 1's K=2
    dt: float = 0.005
    convergence_tol: float = 1e-5
    max_steps: int = 1000          # Sufficient for convergence at K=4+

    # Experiment D
    d_pattern_counts: tuple = (1, 2, 4, 8, 16)
    d_n_trials: int = 20
    d_corruption: float = 0.20

    # Experiment E (K sweep) — P=1 so fast; keep full sweep
    e_k_values: tuple = (1.0, 2.0, 4.0, 8.0, 16.0)
    e_corruption_levels: tuple = (0.1, 0.2, 0.3, 0.4, 0.5)
    e_n_trials: int = 25

    # Experiment F (capacity revisit)
    f_pattern_counts: tuple = (1, 2, 4, 8, 16, 32)
    f_n_trials: int = 15
    f_corruption: float = 0.15

    # Thresholds
    faithful_recall_threshold: float = 0.95   # per-unit cosine ≥ this = faithful
    energy_violation_tol: float = 1e-10
    adaptive_K: bool = True                    # Scale K by N/P


# =============================================================================
# TENSOR-COUPLED TOLS
# =============================================================================

class TangentTOLS:
    """
    Multi-dimensional Kuramoto oscillators with D×D coupling matrices.

    Coupling rule options:
      "scalar_hebbian"    — V0's centered Hebbian (baseline)
      "tensor_hebbian"    — Hebbian in D×D tensor form
      "tensor_pseudo"     — Pseudoinverse in D×D tensor form (new)

    The key innovation in tensor_pseudo:
      Force on unit i:  F_i = K * Proj_{T_{X_i}}(Σ_k alpha_k * p_k^i)
      alpha = G^{-1} @ overlaps
      overlaps_l = Σ_j (p_l^j · X_j)   [Frobenius overlap with current state]
      G_kl = Σ_j (p_k^j · p_l^j)       [Gram matrix]
      Energy = -½ alpha · overlaps

    This requires O(P*N*D) per step — same as scalar case.
    No N^2*D^2 tensor stored explicitly.
    """

    def __init__(
        self,
        n_units: int = 32,
        pattern_dim: int = 8,
        coupling_strength: float = 4.0,
        dt: float = 0.005,
        coupling_rule: str = "tensor_pseudo",
        adaptive_K: bool = True,
        seed: Optional[int] = None,
    ):
        self.n = n_units
        self.dim = pattern_dim
        self.K = coupling_strength
        self.dt = dt
        self.coupling_rule = coupling_rule
        self.adaptive_K = adaptive_K
        self.rng = np.random.RandomState(seed)

        self.X = self.rng.randn(n_units, pattern_dim)
        self.X = self._normalize(self.X)

        # Stored patterns: list of (N, D) unit-vector arrays
        self.patterns: List[np.ndarray] = []
        self._pattern_matrix: np.ndarray = np.zeros((0, n_units, pattern_dim))

        # Pre-computed Gram matrix (K×K) and its inverse
        self.G: Optional[np.ndarray] = None
        self.G_inv: Optional[np.ndarray] = None

        # Scalar W for scalar_hebbian baseline
        self.W_scalar: np.ndarray = np.zeros((n_units, n_units))

        # Instrumentation
        self.energy_log: List[float] = []
        self.order_param_log: List[float] = []
        self.delta_e_log: List[float] = []

    # ----- Utilities -----

    def _normalize(self, X: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(X, axis=1, keepdims=True)
        return X / np.maximum(norms, 1e-12)

    def _effective_K(self) -> float:
        """Adaptive coupling: K * N / max(P, 1) if enabled."""
        if self.adaptive_K and len(self.patterns) > 0:
            return self.K * self.n / len(self.patterns)
        return self.K

    # ----- Storage -----

    def store_pattern(self, pattern: np.ndarray):
        p = self._normalize(pattern.copy())
        self.patterns.append(p)
        self._pattern_matrix = np.stack(self.patterns, axis=0)  # (P, N, D)
        self._rebuild_gram()
        if self.coupling_rule == "scalar_hebbian":
            self._rebuild_scalar_W()

    def _rebuild_gram(self):
        """G_kl = Σ_i (p_k^i · p_l^i) — Frobenius inner product of patterns."""
        P = len(self.patterns)
        if P == 0:
            self.G = None
            self.G_inv = None
            return
        G = np.zeros((P, P))
        for k, pk in enumerate(self.patterns):
            for l, pl in enumerate(self.patterns):
                if l <= k:
                    G[k, l] = np.sum(pk * pl)   # Frobenius: Σ_i p_k^i · p_l^i
                    G[l, k] = G[k, l]
        G += 1e-8 * np.eye(P)   # Regularization
        self.G = G
        self.G_inv = np.linalg.inv(G)

    def _rebuild_scalar_W(self):
        """Centered Hebbian scalar coupling (V0 baseline)."""
        if len(self.patterns) == 0:
            self.W_scalar = np.zeros((self.n, self.n))
            return
        P = np.stack(self.patterns, axis=0)   # (K, N, D)
        mean_p = P.mean(axis=0)               # (N, D)
        W = np.zeros((self.n, self.n))
        for p in self.patterns:
            c = p - mean_p
            norms = np.linalg.norm(c, axis=1, keepdims=True)
            c = c / np.maximum(norms, 1e-12)
            W += c @ c.T
        np.fill_diagonal(W, 0)
        self.W_scalar = W

    # ----- Force Computation -----

    def _overlaps(self) -> np.ndarray:
        """
        overlaps_l = Σ_j (p_l^j · X_j)  [shape: (P,)]
        Vectorized: reshape P_mat to (P, N*D), X to (N*D,), dot product.
        """
        P = len(self.patterns)
        if P == 0:
            return np.zeros(0)
        # _pattern_matrix: (P, N, D) → reshape to (P, N*D)
        PM = self._pattern_matrix.reshape(P, -1)   # (P, N*D)
        XV = self.X.reshape(-1)                     # (N*D,)
        return PM @ XV                              # (P,)

    def _raw_force_tensor_hebbian(self) -> np.ndarray:
        """F_i^raw = K * Σ_k overlaps_k * p_k^i  — vectorized."""
        ovl = self._overlaps()          # (P,)
        K_eff = self._effective_K()
        # (P,) @ (P, N*D) → (N*D,) → (N, D)
        PM = self._pattern_matrix.reshape(len(self.patterns), -1)
        F_flat = ovl @ PM               # (N*D,)
        return K_eff * F_flat.reshape(self.n, self.dim)

    def _raw_force_tensor_pseudo(self) -> np.ndarray:
        """F_i^raw = K * Σ_k alpha_k * p_k^i  — vectorized."""
        if self.G_inv is None:
            return np.zeros((self.n, self.dim))
        ovl = self._overlaps()          # (P,)
        alpha = self.G_inv @ ovl        # (P,)
        K_eff = self._effective_K()
        PM = self._pattern_matrix.reshape(len(self.patterns), -1)
        F_flat = alpha @ PM             # (N*D,)
        return K_eff * F_flat.reshape(self.n, self.dim)

    def _raw_force_scalar_hebbian(self) -> np.ndarray:
        """V0-style scalar coupling force."""
        K_eff = self._effective_K()
        dots = self.X @ self.X.T              # (N, N)
        WX = self.W_scalar @ self.X           # (N, D)
        W_dot_sum = (self.W_scalar * dots).sum(axis=1, keepdims=True)
        return K_eff * (WX - W_dot_sum * self.X)

    def _project_tangent(self, F: np.ndarray) -> np.ndarray:
        """
        Project force vectors onto tangent spaces of S^{D-1} at each X_i.
        Proj_{T_{X_i}}(v) = v - (v · X_i) X_i
        """
        dots = np.sum(F * self.X, axis=1, keepdims=True)   # (N, 1)
        return F - dots * self.X

    # ----- Dynamics -----

    def _step(self):
        if self.coupling_rule == "scalar_hebbian":
            F_tangent = self._raw_force_scalar_hebbian()
        elif self.coupling_rule == "tensor_hebbian":
            F_raw = self._raw_force_tensor_hebbian()
            F_tangent = self._project_tangent(F_raw)
        elif self.coupling_rule == "tensor_pseudo":
            F_raw = self._raw_force_tensor_pseudo()
            F_tangent = self._project_tangent(F_raw)
        else:
            raise ValueError(f"Unknown coupling rule: {self.coupling_rule}")

        self.X = self.X + self.dt * F_tangent
        self.X = self._normalize(self.X)

    # ----- Observables -----

    def compute_energy(self) -> float:
        """
        For tensor rules: E = -½ alpha · overlaps
        For scalar: E = -½ Σ_{ij} W_ij (X_i · X_j)
        """
        if self.coupling_rule == "scalar_hebbian":
            dots = self.X @ self.X.T
            return -0.5 * (self.W_scalar * dots).sum()
        elif self.coupling_rule == "tensor_hebbian":
            ovl = self._overlaps()
            return -0.5 * np.dot(ovl, ovl)
        elif self.coupling_rule == "tensor_pseudo":
            if self.G_inv is None:
                return 0.0
            ovl = self._overlaps()
            alpha = self.G_inv @ ovl
            return -0.5 * np.dot(alpha, ovl)
        return 0.0

    def compute_order_parameter(self) -> float:
        return np.linalg.norm(self.X.mean(axis=0))

    def pattern_similarity(self, state: np.ndarray, pattern: np.ndarray) -> float:
        """Mean per-unit cosine similarity between state and pattern."""
        s = self._normalize(state)
        p = self._normalize(pattern)
        return float(np.mean(np.sum(s * p, axis=1)))

    # ----- Recall -----

    def recall(
        self,
        cue: np.ndarray,
        max_steps: int = 2000,
        tol: float = 1e-5,
        log: bool = True,
    ) -> Tuple[np.ndarray, int, Dict]:
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
            self._step()
            E_now = self.compute_energy()
            delta_e = E_now - E_prev

            if log:
                self.energy_log.append(E_now)
                self.order_param_log.append(self.compute_order_parameter())
                self.delta_e_log.append(delta_e)

            E_prev = E_now
            if np.abs(self.X - X_old).max() < tol:
                break

        violations = sum(1 for d in self.delta_e_log if d > self.energy_violation_tol
                        ) if self.delta_e_log else 0

        return self.X.copy(), step + 1, {
            "converged": step + 1 < max_steps,
            "steps": step + 1,
            "final_energy": E_now,
            "final_R": self.compute_order_parameter(),
            "energy_violations": violations,
            "max_delta_e": max(self.delta_e_log) if self.delta_e_log else 0.0,
        }

    @property
    def energy_violation_tol(self):
        return 1e-10


# =============================================================================
# PATTERN GENERATION (same as Phase 1)
# =============================================================================

def make_random_patterns(P, N, D, rng):
    patterns = []
    for _ in range(P):
        p = rng.randn(N, D)
        p = p / np.linalg.norm(p, axis=1, keepdims=True)
        patterns.append(p)
    return patterns

def make_orthogonal_patterns(P, N, D, rng):
    flat_dim = N * D
    if P > flat_dim:
        raise ValueError(f"Cannot orthogonalize {P} patterns in {flat_dim}D")
    basis = rng.randn(flat_dim, P)
    Q, _ = np.linalg.qr(basis)
    patterns = []
    for i in range(P):
        p = Q[:, i].reshape(N, D)
        p = p / np.linalg.norm(p, axis=1, keepdims=True)
        patterns.append(p)
    return patterns

def corrupt(pattern, rate, rng):
    c = pattern.copy()
    n_corrupt = max(1, int(pattern.shape[0] * rate))
    idx = rng.choice(pattern.shape[0], n_corrupt, replace=False)
    for i in idx:
        v = rng.randn(pattern.shape[1])
        c[i] = v / np.linalg.norm(v)
    return c


# =============================================================================
# EXPERIMENT D: RECONSTRUCTION FIDELITY
# Tensor pseudoinverse vs scalar Hebbian across P=1..16
# Metric: mean per-unit cosine similarity at convergence (not argmax accuracy)
# =============================================================================

def experiment_D_reconstruction(cfg: Phase2Config, seed: int = 42) -> Dict:
    print("\n" + "=" * 72)
    print("EXPERIMENT D: Reconstruction Fidelity (tensor_pseudo vs scalar_hebbian)")
    print("=" * 72)
    print(f"  Corruption: {cfg.d_corruption:.0%} | Trials/pattern: {cfg.d_n_trials}")
    print(f"  Threshold for faithful recall: sim ≥ {cfg.faithful_recall_threshold:.2f}\n")

    results = {}

    for rule in ["scalar_hebbian", "tensor_pseudo"]:
        print(f"  --- {rule.upper()} ---")
        rule_results = {}

        for P in cfg.d_pattern_counts:
            rng = np.random.RandomState(seed)
            patterns = make_orthogonal_patterns(P, cfg.n_units, cfg.pattern_dim, rng)

            net = TangentTOLS(
                n_units=cfg.n_units,
                pattern_dim=cfg.pattern_dim,
                coupling_strength=cfg.base_K,
                dt=cfg.dt,
                coupling_rule=rule,
                adaptive_K=cfg.adaptive_K,
                seed=seed,
            )
            for p in patterns:
                net.store_pattern(p)

            all_sims = []
            faithful = 0
            total = 0

            for pi, target in enumerate(patterns):
                for trial in range(cfg.d_n_trials):
                    trial_rng = np.random.RandomState(seed + pi * 10000 + trial)
                    cue = corrupt(target, cfg.d_corruption, trial_rng)
                    recalled, steps, diag = net.recall(
                        cue, max_steps=cfg.max_steps, tol=cfg.convergence_tol, log=False
                    )
                    sim = net.pattern_similarity(recalled, target)
                    all_sims.append(sim)
                    if sim >= cfg.faithful_recall_threshold:
                        faithful += 1
                    total += 1

            mean_sim = float(np.mean(all_sims))
            faithful_rate = faithful / total
            rule_results[P] = {
                "mean_sim": mean_sim,
                "std_sim": float(np.std(all_sims)),
                "faithful_rate": faithful_rate,
            }
            print(
                f"  P={P:2d}: mean_sim={mean_sim:.3f}±{np.std(all_sims):.3f}  "
                f"faithful={faithful_rate:.3f}"
            )

        results[rule] = rule_results

    # Summary: where does each rule break down?
    print("\n  Reconstruction breakdown (mean_sim < 0.8):")
    for rule in ["scalar_hebbian", "tensor_pseudo"]:
        for P, v in results[rule].items():
            if v["mean_sim"] < 0.80:
                print(f"  {rule}: first failure at P={P} (sim={v['mean_sim']:.3f})")
                break
        else:
            print(f"  {rule}: no failure up to P={max(cfg.d_pattern_counts)}")

    return results


# =============================================================================
# EXPERIMENT E: K SWEEP — BASIN DEPTH VS COUPLING STRENGTH
# =============================================================================

def experiment_E_k_sweep(cfg: Phase2Config, seed: int = 42) -> Dict:
    print("\n" + "=" * 72)
    print("EXPERIMENT E: Basin Depth vs K (tensor_pseudo, P=1)")
    print("=" * 72)

    rng_master = np.random.RandomState(seed)
    target = make_random_patterns(1, cfg.n_units, cfg.pattern_dim, rng_master)[0]

    results = {}

    for K in cfg.e_k_values:
        net = TangentTOLS(
            n_units=cfg.n_units,
            pattern_dim=cfg.pattern_dim,
            coupling_strength=K,
            dt=cfg.dt,
            coupling_rule="tensor_pseudo",
            adaptive_K=False,   # Direct K, no scaling
            seed=seed,
        )
        net.store_pattern(target)

        corruption_results = {}
        for corr in cfg.e_corruption_levels:
            sims = []
            for trial in range(cfg.e_n_trials):
                trial_rng = np.random.RandomState(seed + trial * 100 + int(corr * 1000))
                cue = corrupt(target, corr, trial_rng)
                recalled, _, _ = net.recall(
                    cue, max_steps=cfg.max_steps, tol=cfg.convergence_tol, log=False
                )
                sims.append(net.pattern_similarity(recalled, target))
            corruption_results[corr] = {
                "mean_sim": float(np.mean(sims)),
                "faithful_rate": float(np.mean([s >= cfg.faithful_recall_threshold for s in sims])),
            }

        # Basin radius: largest corruption where faithful_rate ≥ 0.8
        basin_radius = 0.0
        for corr in sorted(cfg.e_corruption_levels):
            if corruption_results[corr]["faithful_rate"] >= 0.80:
                basin_radius = corr
        results[K] = {
            "corruption_results": corruption_results,
            "basin_radius": basin_radius,
        }

        row = "  ".join(
            f"{corr:.0%}:{corruption_results[corr]['mean_sim']:.2f}"
            for corr in cfg.e_corruption_levels
        )
        print(f"  K={K:5.1f}: {row}  | basin_radius={basin_radius:.0%}")

    # Find optimal K
    best_K = max(results, key=lambda k: results[k]["basin_radius"])
    print(f"\n  Optimal K for deepest basin: K={best_K}")

    return results


# =============================================================================
# EXPERIMENT F: CAPACITY WITH TENSOR PSEUDOINVERSE
# =============================================================================

def experiment_F_capacity(cfg: Phase2Config, seed: int = 42) -> Dict:
    print("\n" + "=" * 72)
    print("EXPERIMENT F: Capacity Revisit (tensor_pseudo)")
    print("=" * 72)
    print(f"  Corruption: {cfg.f_corruption:.0%} | Adaptive K: {cfg.adaptive_K}")

    rng = np.random.RandomState(seed)
    results = {}

    for P in cfg.f_pattern_counts:
        if P > cfg.n_units * cfg.pattern_dim:
            break

        patterns = make_orthogonal_patterns(P, cfg.n_units, cfg.pattern_dim, rng)

        net = TangentTOLS(
            n_units=cfg.n_units,
            pattern_dim=cfg.pattern_dim,
            coupling_strength=cfg.base_K,
            dt=cfg.dt,
            coupling_rule="tensor_pseudo",
            adaptive_K=cfg.adaptive_K,
            seed=seed,
        )
        for p in patterns:
            net.store_pattern(p)

        classification_correct = 0
        faithful_correct = 0
        total = 0
        sims_to_target = []

        for pi, target in enumerate(patterns):
            for trial in range(cfg.f_n_trials):
                trial_rng = np.random.RandomState(seed + pi * 50000 + trial)
                cue = corrupt(target, cfg.f_corruption, trial_rng)
                recalled, _, _ = net.recall(
                    cue, max_steps=cfg.max_steps, tol=cfg.convergence_tol, log=False
                )

                # Classification: does recalled lie closest to target?
                sims = [net.pattern_similarity(recalled, q) for q in patterns]
                best_idx = int(np.argmax(sims))
                if best_idx == pi:
                    classification_correct += 1

                # Reconstruction: is the target similarity faithful?
                target_sim = sims[pi]
                sims_to_target.append(target_sim)
                if target_sim >= cfg.faithful_recall_threshold:
                    faithful_correct += 1

                total += 1

        loading_ratio = P / cfg.n_units
        clf_acc = classification_correct / total
        faithful_acc = faithful_correct / total
        mean_sim = float(np.mean(sims_to_target))

        results[P] = {
            "loading_ratio": loading_ratio,
            "classification_acc": clf_acc,
            "faithful_acc": faithful_acc,
            "mean_sim": mean_sim,
        }

        print(
            f"  P={P:2d} (α={loading_ratio:.3f}): "
            f"clf={clf_acc:.3f}  faithful={faithful_acc:.3f}  sim={mean_sim:.3f}"
        )

    # Find where each metric breaks
    print("\n  Phase transitions:")
    for metric, key, thr in [
        ("Classification", "classification_acc", 0.8),
        ("Faithful recall", "faithful_acc", 0.8),
    ]:
        last_good = None
        for P, v in results.items():
            if v[key] >= thr:
                last_good = P
        if last_good is not None:
            print(f"  {metric} ≥ {thr:.0%} holds up to P={last_good} (α={last_good/cfg.n_units:.3f})")
        else:
            print(f"  {metric} never reaches {thr:.0%}")

    return results


# =============================================================================
# ENERGY MONOTONICITY RE-CHECK (tensor coupling)
# =============================================================================

def verify_energy_monotonicity(cfg: Phase2Config, seed: int = 42, n_trials: int = 30) -> bool:
    print("\n" + "=" * 72)
    print("ENERGY CHECK: Monotonicity for tensor_pseudo coupling")
    print("=" * 72)

    rng = np.random.RandomState(seed)
    total_violations = 0
    total_steps = 0

    for trial in range(n_trials):
        patterns = make_random_patterns(2, cfg.n_units, cfg.pattern_dim,
                                        np.random.RandomState(seed + trial))
        net = TangentTOLS(
            n_units=cfg.n_units,
            pattern_dim=cfg.pattern_dim,
            coupling_strength=cfg.base_K,
            dt=cfg.dt,
            coupling_rule="tensor_pseudo",
            adaptive_K=cfg.adaptive_K,
            seed=seed + trial,
        )
        for p in patterns:
            net.store_pattern(p)

        init = rng.randn(cfg.n_units, cfg.pattern_dim)
        init = init / np.linalg.norm(init, axis=1, keepdims=True)
        _, _, diag = net.recall(init, max_steps=cfg.max_steps, log=True)
        total_violations += diag["energy_violations"]
        total_steps += len(net.delta_e_log)

    rate = total_violations / total_steps if total_steps else 0
    passed = total_violations == 0
    print(f"  Trials: {n_trials}  Steps: {total_steps}  Violations: {total_violations}")
    print(f"  {'STRICT PASS' if passed else f'FAIL — rate={rate:.4%}'}")
    return passed


# =============================================================================
# MAIN
# =============================================================================

def run_phase2(seed: int = 42):
    cfg = Phase2Config()

    print("=" * 72)
    print("TOLS v3 — PHASE 2: REDESIGN RESULTS")
    print("Tangent-bundle pseudoinverse + adaptive K")
    print("=" * 72)
    print(f"\nConfig: N={cfg.n_units}, D={cfg.pattern_dim}, K={cfg.base_K}, dt={cfg.dt}")
    print(f"        Adaptive K: {cfg.adaptive_K}, max_steps={cfg.max_steps}")

    t0 = time.time()

    # Gate: verify Lyapunov property holds for tensor coupling
    energy_ok = verify_energy_monotonicity(cfg, seed)
    if not energy_ok:
        print("\n*** WARNING: Energy not monotone for tensor_pseudo. ***")
        print("*** Results below may not represent valid attractor dynamics. ***")

    # Run experiments
    exp_d = experiment_D_reconstruction(cfg, seed)
    exp_e = experiment_E_k_sweep(cfg, seed)
    exp_f = experiment_F_capacity(cfg, seed)

    elapsed = time.time() - t0

    # Final verdict
    print("\n" + "=" * 72)
    print("PHASE 2 VERDICT")
    print("=" * 72)

    # Assess reconstruction quality gain
    pseudo_sims = [v["mean_sim"] for v in exp_d.get("tensor_pseudo", {}).values()]
    scalar_sims = [v["mean_sim"] for v in exp_d.get("scalar_hebbian", {}).values()]
    sim_gain = np.mean(pseudo_sims) - np.mean(scalar_sims) if pseudo_sims and scalar_sims else 0

    # Best basin radius from K sweep
    best_K = max(exp_e, key=lambda k: exp_e[k]["basin_radius"])
    best_basin = exp_e[best_K]["basin_radius"]

    # Capacity: faithful recall capacity
    faithful_capacity = 0
    for P, v in exp_f.items():
        if v["faithful_acc"] >= 0.80:
            faithful_capacity = P

    print(f"\n  Energy monotone (tensor_pseudo): {'YES' if energy_ok else 'NO — INVESTIGATE'}")
    print(f"  Reconstruction gain vs scalar:  {sim_gain:+.3f} mean cosine")
    print(f"  Best basin radius:               {best_basin:.0%} corruption (at K={best_K})")
    print(f"  Faithful recall capacity:        P={faithful_capacity} patterns")

    if sim_gain > 0.05 and best_basin >= 0.30 and faithful_capacity >= 4:
        decision = "ADVANCE TO PHASE 3"
        detail = ("Tensor pseudoinverse delivers faithful reconstruction, "
                  "wide basins, and meaningful capacity. Architecture is viable.")
    elif sim_gain > 0.05 and best_basin >= 0.20:
        decision = "ITERATE K / GEOMETRY"
        detail = ("Reconstruction improved but capacity or basin depth still shallow. "
                  "Try higher K or richer pattern geometry before Phase 3.")
    else:
        decision = "FUNDAMENTAL REDESIGN"
        detail = ("Tensor pseudoinverse did not fix reconstruction. "
                  "Investigate Gram conditioning or manifold structure.")

    print(f"\n  DECISION: {decision}")
    print(f"  {detail}")
    print(f"\n  Elapsed: {elapsed:.1f}s")

    return {
        "energy_ok": energy_ok,
        "exp_d": exp_d,
        "exp_e": exp_e,
        "exp_f": exp_f,
        "decision": decision,
        "best_basin_radius": best_basin,
        "faithful_capacity": faithful_capacity,
        "sim_gain": sim_gain,
    }


if __name__ == "__main__":
    run_phase2(seed=42)

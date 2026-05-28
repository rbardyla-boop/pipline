"""
TOLS v3 — PHASE 4: ADVERSARIAL STRESS TEST
============================================
Phase 3 verdict: VALIDATED. Five targeted attacks on that verdict.

1. MANIFOLD CAPACITY THEORY  — does Gram conditioning predict the cliff?
2. STRUCTURED CORRUPTION     — block, crosstalk, superposition
3. CONTINUAL STORAGE         — catastrophic forgetting under sequential updates
4. REAL DATA RECALL          — transfer beyond synthetic patterns
5. CAPACITY COMPARISON TABLE — situate TOLS v3 against known baselines

Imports TangentTOLS from tols_v3_phase2.py (same directory).
APEX Core 4.3 | VAL Framework v1.0
"""

import numpy as np
import sys
import os
import time
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tols_v3_phase2 import (
    TangentTOLS, make_random_patterns, make_orthogonal_patterns, corrupt
)


# =============================================================================
# CONFIG
# =============================================================================

@dataclass
class Phase4Config:
    pattern_dim: int = 8
    base_K: float = 4.0
    dt: float = 0.005
    convergence_tol: float = 1e-5
    max_steps: int = 1000
    faithful_threshold: float = 0.95

    # Exp 1: Manifold capacity
    exp1_n_units: int = 32
    exp1_p_sweep: tuple = (4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56, 60)
    exp1_n_trials: int = 8
    exp1_corruption: float = 0.15
    exp1_cond_cliff: float = 1e6   # κ(G) threshold for "ill-conditioned"

    # Exp 2: Structured corruption
    exp2_n_units: int = 32
    exp2_n_patterns: int = 4
    exp2_n_trials: int = 20
    exp2_corruption_levels: tuple = (0.1, 0.2, 0.3, 0.4, 0.5)
    exp2_n_superpose: int = 20

    # Exp 3: Continual storage
    exp3_n_units: int = 32
    exp3_max_p: int = 16
    exp3_n_trials: int = 10
    exp3_corruption: float = 0.15

    # Exp 4: Real data
    exp4_n_units: int = 32
    exp4_corruption: float = 0.25
    exp4_n_trials: int = 15

    # Exp 5: Capacity table cliff re-measurement
    exp5_n_units: int = 32
    exp5_p_sweep: tuple = (32, 40, 48, 56, 64)
    exp5_n_trials: int = 10
    exp5_corruption: float = 0.15


# =============================================================================
# NETWORK BUILDER
# =============================================================================

def build_net(N, D, K, patterns, seed=0, adaptive=True):
    net = TangentTOLS(
        n_units=N, pattern_dim=D, coupling_strength=K,
        dt=0.005, coupling_rule="tensor_pseudo",
        adaptive_K=adaptive, seed=seed,
    )
    for p in patterns:
        net.store_pattern(p)
    return net


# =============================================================================
# EXPERIMENT 1: MANIFOLD CAPACITY THEORY
# Does Gram condition number κ(G) predict the capacity cliff?
# =============================================================================

def experiment_1_manifold_capacity(cfg: Phase4Config, seed: int = 42) -> Dict:
    print("\n" + "=" * 72)
    print("EXPERIMENT 1: Manifold Capacity Theory")
    print("=" * 72)
    print(f"  N={cfg.exp1_n_units}, D={cfg.pattern_dim}")
    print(f"  P sweep: {cfg.exp1_p_sweep}")
    print(f"  Corruption: {cfg.exp1_corruption:.0%}, Trials: {cfg.exp1_n_trials}")
    print(f"  Ill-conditioned threshold κ(G) > {cfg.exp1_cond_cliff:.0e}\n")

    N, D = cfg.exp1_n_units, cfg.pattern_dim

    results = {}
    cliff_p_recall = None    # P where faithful recall first drops below 0.80
    cliff_p_cond = None      # P where κ(G) first exceeds threshold

    header = f"  {'P':>4}  {'κ(G)':>12}  {'erank(G)':>10}  {'faithful':>10}  {'mean_sim':>10}"
    print(header)
    print("  " + "-" * (len(header) - 2))

    for P in cfg.exp1_p_sweep:
        if P > N * D:
            print(f"  P={P} > N*D={N*D}, skipping.")
            continue

        rng = np.random.RandomState(seed + P)
        try:
            patterns = make_orthogonal_patterns(P, N, D, rng)
        except ValueError as e:
            print(f"  P={P}: {e}, skipping.")
            continue

        # Gram matrix and conditioning
        net = build_net(N, D, cfg.base_K, patterns, seed=seed, adaptive=True)

        try:
            G = net.G
            eigvals = np.linalg.eigvalsh(G)
            eigvals = np.sort(eigvals)[::-1]
            cond_G = float(eigvals[0] / max(eigvals[-1], 1e-15))
            erank = int(np.sum(eigvals > 0.01 * eigvals[0]))
        except np.linalg.LinAlgError as e:
            print(f"  P={P}: Gram eigendecomposition failed: {e}")
            cond_G = float("inf")
            erank = -1

        # Also check pairwise off-diagonal similarity after per-unit normalization
        P_mat = net._pattern_matrix.reshape(P, -1)   # (P, N*D)
        gram_normalized = P_mat @ P_mat.T             # (P, P)
        diag_mask = np.eye(P, dtype=bool)
        off_diag = gram_normalized[~diag_mask]
        mean_cross = float(np.mean(np.abs(off_diag)))

        # Faithful recall
        faithful = 0
        total = 0
        sims = []

        for pi, target in enumerate(patterns[:min(P, 8)]):   # cap at 8 patterns for speed
            for trial in range(cfg.exp1_n_trials):
                trial_rng = np.random.RandomState(seed + P * 1000 + pi * 100 + trial)
                cue = corrupt(target, cfg.exp1_corruption, trial_rng)
                try:
                    recalled, _, _ = net.recall(
                        cue, max_steps=cfg.max_steps, tol=cfg.convergence_tol, log=False
                    )
                    sim = net.pattern_similarity(recalled, target)
                    sims.append(sim)
                    if sim >= cfg.faithful_threshold:
                        faithful += 1
                except np.linalg.LinAlgError:
                    sims.append(0.0)
                total += 1

        faithful_rate = faithful / total if total > 0 else 0.0
        mean_sim = float(np.mean(sims)) if sims else 0.0

        results[P] = {
            "cond_G": cond_G,
            "erank_G": erank,
            "mean_cross_sim": mean_cross,
            "faithful_rate": faithful_rate,
            "mean_sim": mean_sim,
        }

        if cliff_p_recall is None and faithful_rate < 0.80:
            cliff_p_recall = P
        if cliff_p_cond is None and cond_G > cfg.exp1_cond_cliff:
            cliff_p_cond = P

        cond_str = f"{cond_G:.2e}" if np.isfinite(cond_G) else "     inf"
        print(
            f"  {P:>4}  {cond_str:>12}  {erank:>10}  "
            f"{faithful_rate:>10.3f}  {mean_sim:>10.3f}"
        )

    # Verdict
    print(f"\n  --- VERDICT ---")
    print(f"  Recall cliff (faithful < 0.80):  P={cliff_p_recall}")
    print(f"  Gram cliff (κ > {cfg.exp1_cond_cliff:.0e}):        P={cliff_p_cond}")

    if cliff_p_recall is not None and cliff_p_cond is not None:
        aligned = abs(cliff_p_recall - cliff_p_cond) <= 8   # within 2 steps
        if aligned:
            verdict = "PASS"
            print(f"  PASS: Gram conditioning predicts capacity cliff (within 2 steps).")
        else:
            verdict = "FAIL"
            print(f"  FAIL: Recall cliff (P={cliff_p_recall}) ≠ Gram cliff (P={cliff_p_cond}).")
            print(f"        Gram conditioning does not explain the cliff location.")
    elif cliff_p_recall is None:
        verdict = "INCONCLUSIVE"
        print(f"  INCONCLUSIVE: No recall cliff found in P={cfg.exp1_p_sweep}.")
    else:
        verdict = "FAIL"
        print(f"  FAIL: Recall cliff at P={cliff_p_recall} but Gram remains well-conditioned.")

    return {
        "per_p": results,
        "cliff_p_recall": cliff_p_recall,
        "cliff_p_cond": cliff_p_cond,
        "verdict": verdict,
    }


# =============================================================================
# STRUCTURED CORRUPTION HELPERS
# =============================================================================

def block_corrupt(pattern: np.ndarray, rate: float, rng: np.random.RandomState) -> np.ndarray:
    """Replace contiguous block of units 0..floor(N*rate) with random unit vectors."""
    corrupted = pattern.copy()
    n_corrupt = max(1, int(pattern.shape[0] * rate))
    for i in range(n_corrupt):
        v = rng.randn(pattern.shape[1])
        corrupted[i] = v / np.linalg.norm(v)
    return corrupted


def crosstalk_corrupt(target: np.ndarray, distractor: np.ndarray, rate: float) -> np.ndarray:
    """Per-unit: normalize((1-rate)*target_i + rate*distractor_i)."""
    blend = (1 - rate) * target + rate * distractor
    norms = np.linalg.norm(blend, axis=1, keepdims=True)
    return blend / np.maximum(norms, 1e-12)


def superpose(pattern_a: np.ndarray, pattern_b: np.ndarray) -> np.ndarray:
    """Per-unit: normalize(0.5*a_i + 0.5*b_i)."""
    blend = 0.5 * pattern_a + 0.5 * pattern_b
    norms = np.linalg.norm(blend, axis=1, keepdims=True)
    return blend / np.maximum(norms, 1e-12)


# =============================================================================
# EXPERIMENT 2: STRUCTURED CORRUPTION
# =============================================================================

def experiment_2_structured_corruption(cfg: Phase4Config, seed: int = 42) -> Dict:
    print("\n" + "=" * 72)
    print("EXPERIMENT 2: Structured Corruption")
    print("=" * 72)
    print(f"  N={cfg.exp2_n_units}, D={cfg.pattern_dim}, P={cfg.exp2_n_patterns}")
    print(f"  (a) Block  (b) Crosstalk  (c) Superposition\n")

    N, D, P = cfg.exp2_n_units, cfg.pattern_dim, cfg.exp2_n_patterns
    rng = np.random.RandomState(seed)
    patterns = make_orthogonal_patterns(P, N, D, rng)
    net = build_net(N, D, cfg.base_K, patterns, seed=seed, adaptive=True)

    results = {}

    # --- (a) Block corruption ---
    print("  (a) BLOCK CORRUPTION (contiguous unit replacement):")
    block_results = {}
    for rate in cfg.exp2_corruption_levels:
        faithful = 0
        total = 0
        sims = []
        for pi, target in enumerate(patterns):
            for trial in range(cfg.exp2_n_trials):
                trial_rng = np.random.RandomState(seed + pi * 10000 + trial + int(rate * 1e5))
                cue = block_corrupt(target, rate, trial_rng)
                recalled, _, _ = net.recall(
                    cue, max_steps=cfg.max_steps, tol=cfg.convergence_tol, log=False
                )
                sim = net.pattern_similarity(recalled, target)
                sims.append(sim)
                if sim >= cfg.faithful_threshold:
                    faithful += 1
                total += 1

        faithful_rate = faithful / total
        mean_sim = float(np.mean(sims))
        block_results[rate] = {"faithful_rate": faithful_rate, "mean_sim": mean_sim}
        print(f"    rate={rate:.0%}: faithful={faithful_rate:.3f}  sim={mean_sim:.3f}")

    block_pass = all(
        block_results[r]["faithful_rate"] >= 0.80
        for r in cfg.exp2_corruption_levels if r <= 0.30
    )
    print(f"    Block 30% verdict: {'PASS' if block_pass else 'FAIL'}")
    results["block"] = {"per_rate": block_results, "pass": block_pass}

    # --- (b) Crosstalk corruption ---
    print("\n  (b) CROSSTALK CORRUPTION (blend with another stored pattern):")
    cross_results = {}
    for rate in cfg.exp2_corruption_levels:
        faithful = 0
        total = 0
        sims = []
        for pi, target in enumerate(patterns):
            distractor_idx = (pi + 1) % P
            distractor = patterns[distractor_idx]
            for trial in range(cfg.exp2_n_trials):
                cue = crosstalk_corrupt(target, distractor, rate)
                recalled, _, _ = net.recall(
                    cue, max_steps=cfg.max_steps, tol=cfg.convergence_tol, log=False
                )
                sim = net.pattern_similarity(recalled, target)
                sims.append(sim)
                if sim >= cfg.faithful_threshold:
                    faithful += 1
                total += 1

        faithful_rate = faithful / total
        mean_sim = float(np.mean(sims))
        cross_results[rate] = {"faithful_rate": faithful_rate, "mean_sim": mean_sim}
        print(f"    rate={rate:.0%}: faithful={faithful_rate:.3f}  sim={mean_sim:.3f}")

    cross_pass = all(
        cross_results[r]["faithful_rate"] >= 0.80
        for r in cfg.exp2_corruption_levels if r <= 0.30
    )
    print(f"    Crosstalk 30% verdict: {'PASS' if cross_pass else 'FAIL'}")
    results["crosstalk"] = {"per_rate": cross_results, "pass": cross_pass}

    # --- (c) Superposition ---
    print("\n  (c) SUPERPOSITION (50/50 blend of two stored patterns):")
    rng2 = np.random.RandomState(seed + 99)
    wins = {i: 0 for i in range(P)}
    no_winner = 0
    margins = []

    for trial in range(cfg.exp2_n_superpose):
        # Pick two random patterns to superpose
        idx_a, idx_b = rng2.choice(P, 2, replace=False)
        pa, pb = patterns[idx_a], patterns[idx_b]
        cue = superpose(pa, pb)

        recalled, _, _ = net.recall(
            cue, max_steps=cfg.max_steps, tol=cfg.convergence_tol, log=False
        )

        # Measure similarity to all patterns
        all_sims = [net.pattern_similarity(recalled, q) for q in patterns]
        best_idx = int(np.argmax(all_sims))
        best_sim = all_sims[best_idx]
        sorted_sims = sorted(all_sims, reverse=True)
        margin = sorted_sims[0] - sorted_sims[1]

        if best_sim >= 0.90:
            wins[best_idx] += 1
            margins.append(margin)
        else:
            no_winner += 1

    total_trials = cfg.exp2_n_superpose
    resolved = total_trials - no_winner
    mean_margin = float(np.mean(margins)) if margins else 0.0

    print(f"    Trials: {total_trials}")
    print(f"    Resolved to single pattern: {resolved}/{total_trials} ({resolved/total_trials:.0%})")
    print(f"    Unresolved (no pattern ≥ 0.90): {no_winner}")
    print(f"    Mean margin over 2nd place: {mean_margin:.3f}")
    win_counts = {k: v for k, v in wins.items() if v > 0}
    print(f"    Winner distribution: {win_counts}")

    super_pass = (resolved / total_trials) >= 0.80 and mean_margin > 0.05
    print(f"    Superposition verdict: {'PASS' if super_pass else 'FAIL'}")
    results["superposition"] = {
        "resolved_rate": resolved / total_trials,
        "mean_margin": mean_margin,
        "no_winner": no_winner,
        "pass": super_pass,
    }

    overall_pass = block_pass and cross_pass and super_pass
    print(f"\n  EXPERIMENT 2 OVERALL: {'PASS' if overall_pass else 'FAIL'}")

    return results


# =============================================================================
# EXPERIMENT 3: CONTINUAL STORAGE
# Catastrophic forgetting under sequential pattern updates
# =============================================================================

def experiment_3_continual_storage(cfg: Phase4Config, seed: int = 42) -> Dict:
    print("\n" + "=" * 72)
    print("EXPERIMENT 3: Continual Storage (Catastrophic Forgetting Test)")
    print("=" * 72)
    P_max = cfg.exp3_max_p
    N, D = cfg.exp3_n_units, cfg.pattern_dim
    print(f"  N={N}, D={D}, max_P={P_max}, corruption={cfg.exp3_corruption:.0%}\n")

    rng = np.random.RandomState(seed)
    all_patterns = make_orthogonal_patterns(P_max, N, D, rng)

    # M[i][j] = mean_sim of pattern j after i+1 patterns stored (j <= i)
    # Shape: (P_max, P_max), lower triangular
    M = np.full((P_max, P_max), np.nan)
    min_sim_overall = 1.0
    forgetting_event = None   # (i, j, sim) of first catastrophic drop

    # Print header
    print("  Similarity matrix M[P_stored][pattern_idx] (rows=stored, cols=pattern):")
    header_cols = "  " + "".join(f"p{j+1:02d}   " for j in range(P_max))
    print(header_cols)

    for i in range(P_max):
        # Build network with i+1 patterns
        net = build_net(N, D, cfg.base_K, all_patterns[:i+1], seed=seed, adaptive=True)

        row_sims = []
        for j in range(i + 1):
            target = all_patterns[j]
            trial_sims = []
            for trial in range(cfg.exp3_n_trials):
                trial_rng = np.random.RandomState(seed + i * 1000 + j * 100 + trial)
                cue = corrupt(target, cfg.exp3_corruption, trial_rng)
                recalled, _, _ = net.recall(
                    cue, max_steps=cfg.max_steps, tol=cfg.convergence_tol, log=False
                )
                trial_sims.append(net.pattern_similarity(recalled, target))

            sim = float(np.mean(trial_sims))
            M[i][j] = sim
            row_sims.append(sim)

            if sim < min_sim_overall:
                min_sim_overall = sim
            if forgetting_event is None and sim < 0.90 and j < i:
                forgetting_event = (i + 1, j + 1, sim)

        # Print row
        row_str = "  " + "".join(
            f"{M[i][j]:.3f} " if not np.isnan(M[i][j]) else "  --- "
            for j in range(P_max)
        )
        print(f"  P={i+1:02d}: {row_str}")

    # Verdict
    print(f"\n  --- VERDICT ---")
    print(f"  Minimum similarity across all (P_stored, pattern) pairs: {min_sim_overall:.4f}")
    print(f"  Threshold for catastrophic forgetting: < 0.90")

    if forgetting_event:
        i_ev, j_ev, sim_ev = forgetting_event
        verdict = "FAIL"
        print(f"  FAIL: Catastrophic forgetting at P_stored={i_ev}, pattern {j_ev} "
              f"dropped to sim={sim_ev:.3f}")
    elif min_sim_overall >= 0.90:
        verdict = "PASS"
        print(f"  PASS: All patterns maintained above 0.90 similarity throughout sequential storage.")
    else:
        verdict = "FAIL"
        print(f"  FAIL: Minimum similarity {min_sim_overall:.3f} < 0.90.")

    return {
        "M": M.tolist(),
        "min_sim": min_sim_overall,
        "forgetting_event": forgetting_event,
        "verdict": verdict,
    }


# =============================================================================
# EXPERIMENT 4: REAL DATA RECALL
# =============================================================================

def _try_load_mnist(n_classes: int, n_units: int, pattern_dim: int, seed: int):
    """
    Attempt to load MNIST via sklearn. Returns (patterns, labels, source_str)
    or raises ImportError/Exception if unavailable.
    """
    from sklearn.datasets import fetch_openml
    mnist = fetch_openml("mnist_784", version=1, as_frame=False, cache=True)
    X, y = mnist.data.astype(np.float32), mnist.target.astype(int)

    rng = np.random.RandomState(seed)
    prototypes = []
    for cls in range(n_classes):
        idx = np.where(y == cls)[0]
        mean_img = X[idx].mean(axis=0)   # (784,)
        # PCA to reduce to n_units * pattern_dim dimensions
        # Use a simple projection: tile the 784-dim vector into (n_units, pattern_dim)
        # via chunked averaging
        flat_dim = n_units * pattern_dim   # 256 for N=32, D=8
        if len(mean_img) > flat_dim:
            # Reshape 784 → 256 via average pooling over 3-pixel blocks
            factor = len(mean_img) // flat_dim
            remainder = len(mean_img) % flat_dim
            # Trim to exact multiple
            trimmed = mean_img[:flat_dim * factor]
            pooled = trimmed.reshape(flat_dim, factor).mean(axis=1)
        else:
            pooled = mean_img[:flat_dim]

        # Reshape to (n_units, pattern_dim)
        p = pooled.reshape(n_units, pattern_dim)
        # Add small noise to avoid degenerate zero-norms
        p += rng.randn(*p.shape) * 0.01
        norms = np.linalg.norm(p, axis=1, keepdims=True)
        p = p / np.maximum(norms, 1e-12)
        prototypes.append(p)

    return prototypes, list(range(n_classes)), "MNIST"


def _synthetic_digit_patterns(n_classes: int, n_units: int, pattern_dim: int, seed: int):
    """
    Generate synthetic digit-like patterns using structured Gaussian clusters.
    Each class has a distinctive 'activation region' in unit space.
    Prints a [SIMULATED] warning.
    """
    print("  [SIMULATED] MNIST unavailable. Using synthetic digit-like patterns.")
    print("  Each class = structured Gaussian centroid in R^{N*D}, normalized per unit.")
    rng = np.random.RandomState(seed)
    flat_dim = n_units * pattern_dim

    prototypes = []
    for cls in range(n_classes):
        # Create a structured base vector: each class has a dominant block
        v = rng.randn(flat_dim) * 0.2   # small background noise
        # Primary activation region: cls-th tenth of the flat space
        block_size = flat_dim // n_classes
        start = cls * block_size
        v[start:start + block_size] += rng.randn(block_size) * 2.0
        # Secondary activation for variability
        sec = (cls * 7 + 13) % flat_dim
        v[sec:sec + block_size // 2] += rng.randn(block_size // 2) * 1.0

        p = v.reshape(n_units, pattern_dim)
        norms = np.linalg.norm(p, axis=1, keepdims=True)
        p = p / np.maximum(norms, 1e-12)
        prototypes.append(p)

    return prototypes, list(range(n_classes)), "[SIMULATED]"


def experiment_4_real_data(cfg: Phase4Config, seed: int = 42) -> Dict:
    print("\n" + "=" * 72)
    print("EXPERIMENT 4: Real Data Recall")
    print("=" * 72)
    N, D = cfg.exp4_n_units, cfg.pattern_dim

    # Load MNIST or fall back to synthetic
    try:
        prototypes, labels, source = _try_load_mnist(10, N, D, seed)
        print(f"  Source: {source}")
    except Exception as e:
        print(f"  MNIST load failed ({type(e).__name__}). Falling back to synthetic.")
        prototypes, labels, source = _synthetic_digit_patterns(10, N, D, seed)

    n_classes = len(prototypes)
    print(f"  Classes: {n_classes}, Corruption: {cfg.exp4_corruption:.0%}, "
          f"Trials/class: {cfg.exp4_n_trials}")
    if source == "[SIMULATED]":
        print("  NOTE: All metrics below are marked [SIMULATED].")
    print()

    # Store all class prototypes
    net = build_net(N, D, cfg.base_K, prototypes, seed=seed, adaptive=True)
    gram_cond = float(np.linalg.cond(net.G)) if net.G is not None else float("inf")
    print(f"  Gram condition number: {gram_cond:.2e}")

    # Recall from occluded versions (zero out contiguous block)
    classification_correct = 0
    faithful_correct = 0
    total = 0
    per_class = {}

    for cls_idx, target in enumerate(prototypes):
        cls_clf = 0
        cls_faithful = 0
        cls_sims = []

        for trial in range(cfg.exp4_n_trials):
            trial_rng = np.random.RandomState(seed + cls_idx * 1000 + trial)
            # Occlusion: zero out first 25% of units (contiguous block)
            cue = block_corrupt(target, cfg.exp4_corruption, trial_rng)
            recalled, _, _ = net.recall(
                cue, max_steps=cfg.max_steps, tol=cfg.convergence_tol, log=False
            )

            all_sims = [net.pattern_similarity(recalled, p) for p in prototypes]
            best_idx = int(np.argmax(all_sims))
            target_sim = all_sims[cls_idx]

            cls_sims.append(target_sim)
            if best_idx == cls_idx:
                cls_clf += 1
                classification_correct += 1
            if target_sim >= cfg.faithful_threshold:
                cls_faithful += 1
                faithful_correct += 1
            total += 1

        per_class[cls_idx] = {
            "clf_rate": cls_clf / cfg.exp4_n_trials,
            "faithful_rate": cls_faithful / cfg.exp4_n_trials,
            "mean_sim": float(np.mean(cls_sims)),
        }

    overall_clf = classification_correct / total
    overall_faithful = faithful_correct / total

    sim_tag = source if source == "[SIMULATED]" else ""
    print(f"  {'Class':<8} {'CLF':>8} {'Faithful':>10} {'Sim':>8}")
    print("  " + "-" * 40)
    for cls_idx, v in per_class.items():
        tag = sim_tag if sim_tag else ""
        print(f"  cls={cls_idx:<4} {v['clf_rate']:>8.3f} {v['faithful_rate']:>10.3f} "
              f"{v['mean_sim']:>8.3f}  {tag}")

    print(f"\n  Overall classification: {overall_clf:.3f}")
    print(f"  Overall faithful recall: {overall_faithful:.3f}")

    verdict_tag = f" {source}" if source == "[SIMULATED]" else ""
    if overall_clf >= 0.90:
        verdict = "PASS"
        print(f"  PASS{verdict_tag}: Classification ≥ 90%.")
    else:
        verdict = "FAIL"
        print(f"  FAIL{verdict_tag}: Classification {overall_clf:.0%} < 90%.")

    return {
        "source": source,
        "overall_clf": overall_clf,
        "overall_faithful": overall_faithful,
        "gram_cond": gram_cond,
        "per_class": per_class,
        "verdict": verdict,
    }


# =============================================================================
# EXPERIMENT 5: CAPACITY COMPARISON TABLE
# =============================================================================

def _measure_tols_pmax(cfg: Phase4Config, seed: int = 42) -> Tuple[int, float]:
    """
    Re-measure TOLS v3 capacity cliff at N=32: find max P with faithful ≥ 0.80.
    Returns (P_max_measured, alpha_max).
    """
    N, D = cfg.exp5_n_units, cfg.pattern_dim
    last_good_P = 0

    for P in cfg.exp5_p_sweep:
        if P > N * D:
            break
        rng = np.random.RandomState(seed + P)
        try:
            patterns = make_orthogonal_patterns(P, N, D, rng)
        except ValueError:
            break

        net = build_net(N, D, cfg.base_K, patterns, seed=seed, adaptive=True)

        faithful = 0
        total = 0
        for pi, target in enumerate(patterns[:min(P, 6)]):
            for trial in range(cfg.exp5_n_trials):
                trial_rng = np.random.RandomState(seed + P * 1000 + pi * 100 + trial)
                cue = corrupt(target, cfg.exp5_corruption, trial_rng)
                try:
                    recalled, _, _ = net.recall(
                        cue, max_steps=cfg.max_steps, tol=cfg.convergence_tol, log=False
                    )
                    sim = net.pattern_similarity(recalled, target)
                    if sim >= 0.95:
                        faithful += 1
                except np.linalg.LinAlgError:
                    pass
                total += 1

        faithful_rate = faithful / total if total > 0 else 0.0
        if faithful_rate >= 0.80:
            last_good_P = P

    alpha = last_good_P / N if last_good_P > 0 else 0.0
    return last_good_P, alpha


def experiment_5_capacity_table(cfg: Phase4Config, seed: int = 42) -> Dict:
    print("\n" + "=" * 72)
    print("EXPERIMENT 5: Capacity Comparison Table")
    print("=" * 72)

    N, D = cfg.exp5_n_units, cfg.pattern_dim
    n_dof_tols = N * D    # Each oscillator has D-dimensional state

    print(f"  Measuring TOLS v3 P_max at N={N}, D={D}...")
    tols_pmax, tols_alpha = _measure_tols_pmax(cfg, seed)
    tols_capacity_per_dof = tols_pmax / n_dof_tols

    print(f"  TOLS v3 P_max = {tols_pmax} (α = {tols_alpha:.2f})\n")

    # -------------------------------------------------------------------------
    # Baseline definitions
    # Sources cited inline. Uncertainty noted where applicable.
    # -------------------------------------------------------------------------

    rows = [
        {
            "system": "TOLS v3 (this work)",
            "capacity_formula": f"~{tols_alpha:.1f}·N",
            "P_at_N32": str(tols_pmax),
            "capacity_per_dof": f"{tols_capacity_per_dof:.3f}",
            "energy_guarantee": "YES (strict)",
            "state_space": f"(S^{{D-1}})^N, D={D}",
            "notes": f"Measured, orthogonal patterns, N={N}",
        },
        {
            "system": "Classical Hopfield",
            "capacity_formula": "≈0.138·N",
            "P_at_N32": f"~{int(0.138 * N)}",
            "capacity_per_dof": "0.138",
            "energy_guarantee": "YES (Lyapunov)",
            "state_space": "{±1}^N, 1 DoF/unit",
            "notes": "Amit, Gutfreund & Sompolinsky (1985), Phys Rev A 32:1007. "
                     "Perfect recall limit T→0. With errors: ≈N/(2 ln N).",
        },
        {
            "system": "Modern Hopfield (Ramsauer+)",
            "capacity_formula": "~exp(β²Δ²/8) for separation Δ",
            "P_at_N32": "exponential in β",
            "capacity_per_dof": "model-dependent",
            "energy_guarantee": "YES (softmax energy)",
            "state_space": "R^D continuous",
            "notes": "Ramsauer et al. (2020), arXiv:2008.02217. "
                     "Capacity is exponential in inverse temperature β and "
                     "minimum pattern separation Δ. Exact P_max depends on "
                     "pattern geometry — not directly comparable at N=32.",
        },
        {
            "system": "Dense Assoc. Memory (n=3)",
            "capacity_formula": "O(N²)",
            "P_at_N32": f"~{N**2 // 2}",
            "capacity_per_dof": f"~{N // 2:.0f}x Hopfield",
            "energy_guarantee": "YES (polynomial energy)",
            "state_space": "{±1}^N, 1 DoF/unit",
            "notes": "Krotov & Hopfield (2016), arXiv:1606.01164. "
                     "n-th order interactions give P ∝ N^{n-1}. n=3: P ∝ N². "
                     "P_at_N32 is O(N²/2) = 512; exact prefactor varies by setting. "
                     "UNCERTAINTY: exact prefactor from paper depends on error criterion.",
        },
    ]

    # Print table
    cols = [
        ("System", 30),
        ("P formula", 26),
        ("P (N=32)", 10),
        ("P/DoF", 8),
        ("Energy", 8),
        ("Notes (truncated)", 45),
    ]

    def sep():
        print("  " + "+".join("-" * (w + 2) for _, w in cols))

    def row_str(vals):
        return "  " + "|".join(
            f" {str(v)[:w]:<{w}} " for v, (_, w) in zip(vals, cols)
        )

    sep()
    print(row_str([h for h, _ in cols]))
    sep()
    for r in rows:
        print(row_str([
            r["system"],
            r["capacity_formula"],
            r["P_at_N32"],
            r["capacity_per_dof"],
            r["energy_guarantee"],
            r["notes"],
        ]))
    sep()

    print("""
  METHODOLOGICAL NOTE:
  "Capacity/DoF" is NOT a universal comparison metric. Classical Hopfield has
  1 binary DoF per unit; TOLS v3 has D=8 continuous DoF per unit. A pattern
  in TOLS v3 specifies 8 floating-point values per unit, vs 1 bit per unit in
  Hopfield. Normalizing by total DoF penalizes richer state spaces.

  The meaningful comparison is capacity at fixed N:
    Classical Hopfield  :  P_max ≈  4   (at N=32)
    TOLS v3 (measured)  :  P_max = {tols_pmax}  (at N=32, D=8)
    Dense AM (n=3)      :  P_max ≈ 512  (at N=32, theoretical)
    Modern Hopfield     :  exponential in β (not directly bounded by N alone)

  TOLS v3 occupies a middle ground: far above classical Hopfield per unit,
  below polynomial-order dense memories, with a strict Lyapunov guarantee.
  The DoF cost (D=8) is the price of the manifold structure.
""".format(tols_pmax=tols_pmax))

    return {
        "tols_pmax": tols_pmax,
        "tols_alpha": tols_alpha,
        "tols_capacity_per_dof": tols_capacity_per_dof,
        "table_rows": rows,
        "verdict": "COMPLETE",
    }


# =============================================================================
# MAIN: PHASE 4 REPORT
# =============================================================================

def run_phase4(seed: int = 42):
    cfg = Phase4Config()

    print("=" * 72)
    print("TOLS v3 — PHASE 4: ADVERSARIAL STRESS TEST")
    print("V0 Falsification Testbed | APEX Core 4.3")
    print("=" * 72)
    print(f"\nConfig: N={cfg.exp1_n_units}, D={cfg.pattern_dim}, K={cfg.base_K}, dt={cfg.dt}")

    t0 = time.time()

    exp1 = experiment_1_manifold_capacity(cfg, seed)
    exp2 = experiment_2_structured_corruption(cfg, seed)
    exp3 = experiment_3_continual_storage(cfg, seed)
    exp4 = experiment_4_real_data(cfg, seed)
    exp5 = experiment_5_capacity_table(cfg, seed)

    elapsed = time.time() - t0

    # Summary
    print("\n" + "=" * 72)
    print("PHASE 4 SUMMARY TABLE")
    print("=" * 72)
    print(f"\n  {'Experiment':<40} {'Verdict':<12} {'Key Metric'}")
    print("  " + "-" * 70)

    rows_summary = [
        ("1. Manifold Capacity Theory",
         exp1["verdict"],
         f"Recall cliff P={exp1['cliff_p_recall']}  Gram cliff P={exp1['cliff_p_cond']}"),
        ("2a. Block Corruption",
         "PASS" if exp2["block"]["pass"] else "FAIL",
         f"Faithful@30%={exp2['block']['per_rate'].get(0.3, {}).get('faithful_rate', 0):.3f}"),
        ("2b. Crosstalk Corruption",
         "PASS" if exp2["crosstalk"]["pass"] else "FAIL",
         f"Faithful@30%={exp2['crosstalk']['per_rate'].get(0.3, {}).get('faithful_rate', 0):.3f}"),
        ("2c. Superposition",
         "PASS" if exp2["superposition"]["pass"] else "FAIL",
         f"Resolved={exp2['superposition']['resolved_rate']:.2f}  "
         f"Margin={exp2['superposition']['mean_margin']:.3f}"),
        ("3. Continual Storage",
         exp3["verdict"],
         f"Min sim={exp3['min_sim']:.4f}  "
         f"{'No forgetting' if exp3['forgetting_event'] is None else str(exp3['forgetting_event'])}"),
        ("4. Real Data Recall",
         exp4["verdict"],
         f"CLF={exp4['overall_clf']:.3f}  Faithful={exp4['overall_faithful']:.3f}  "
         f"[{exp4['source']}]"),
        ("5. Capacity Table",
         "COMPLETE",
         f"TOLS P_max={exp5['tols_pmax']} (α={exp5['tols_alpha']:.2f})"),
    ]

    pass_count = 0
    fail_count = 0
    for name, verdict, metric in rows_summary:
        print(f"  {name:<40} {verdict:<12} {metric}")
        if "PASS" in verdict:
            pass_count += 1
        elif "FAIL" in verdict:
            fail_count += 1

    print(f"\n  PASS: {pass_count}  FAIL: {fail_count}")
    print(f"  Elapsed: {elapsed:.1f}s")

    return {
        "exp1": exp1, "exp2": exp2, "exp3": exp3, "exp4": exp4, "exp5": exp5,
    }


if __name__ == "__main__":
    run_phase4(seed=42)

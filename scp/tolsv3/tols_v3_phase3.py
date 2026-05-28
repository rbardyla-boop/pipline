"""
TOLS v3 — PHASE 3: ADVERSARIAL STRESS TEST
=============================================
Phase 2 verdict: ADVANCE. Tensor pseudoinverse achieves sim=0.991 at P=32.

Phase 3 goal: Find the failure boundary.

Three hypotheses to falsify:

  H1 — ORTHOGONAL-ONLY ILLUSION
    Phase 2 used orthogonal patterns exclusively. Correlated patterns
    will degrade the Gram condition number and may destroy recall.
    If this fails, the architecture is a lab trick.

  H2 — PHANTOM BASINS
    Phase 2 tested convergence (max state change < tol), not stability.
    A metastable state may pass the convergence check, then drift away.
    If the recalled state doesn't survive perturbation, it's a transient.

  H3 — SCALE COLLAPSE
    N=32 is toy-scale. Does alpha=1.0 capacity hold at N=64, 128, 256?
    Does the Gram inverse become ill-conditioned at scale?

Each experiment has explicit pass/fail and logs the Gram condition number
as a diagnostic throughout.

APEX Core 4.3 | VAL Framework v1.0
"""

import numpy as np
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
import time
import sys
import os

# Import Phase 2's TangentTOLS and helpers
sys.path.insert(0, "/mnt/user-data/uploads")
from tols_v3_phase2 import (
    TangentTOLS, make_random_patterns, make_orthogonal_patterns, corrupt,
    Phase2Config
)


# =============================================================================
# PHASE 3 CONFIG
# =============================================================================

@dataclass
class Phase3Config:
    # Base architecture
    pattern_dim: int = 8
    base_K: float = 4.0
    dt: float = 0.005
    convergence_tol: float = 1e-5
    max_steps: int = 1000
    faithful_threshold: float = 0.95

    # Experiment G: Correlated patterns
    g_n_units: int = 32
    g_pattern_count: int = 8
    g_n_trials: int = 10
    g_corruption: float = 0.20
    g_correlation_levels: tuple = (0.0, 0.3, 0.5, 0.7, 0.9)

    # Experiment H: Post-convergence stability
    h_n_units: int = 32
    h_pattern_count: int = 4
    h_perturbation_magnitude: float = 0.05  # re-kick after convergence
    h_post_convergence_steps: int = 500     # run this many more steps
    h_n_trials: int = 15
    h_stability_threshold: float = 0.99     # sim to pre-perturbation state

    # Experiment I: Scale-up
    i_n_values: tuple = (32, 64, 128)
    i_loading_ratios: tuple = (0.25, 0.5)
    i_n_trials: int = 10
    i_corruption: float = 0.15


# =============================================================================
# CORRELATED PATTERN GENERATION
# =============================================================================

def make_correlated_patterns(
    P: int, N: int, D: int, correlation: float, rng: np.random.RandomState
) -> List[np.ndarray]:
    """
    Generate P patterns with controlled inter-pattern correlation.

    Method:
      1. Generate one 'base' direction in (N*D)-space.
      2. Each pattern = correlation * base + sqrt(1 - correlation^2) * noise.
      3. Normalize per unit to S^{D-1}.

    correlation=0.0 → independent random patterns (like make_random_patterns)
    correlation=0.9 → highly similar patterns (hard for any memory system)

    Returns patterns and the pairwise Frobenius similarity matrix for diagnostics.
    """
    flat_dim = N * D
    base = rng.randn(flat_dim)
    base = base / np.linalg.norm(base)

    patterns = []
    for _ in range(P):
        noise = rng.randn(flat_dim)
        noise = noise / np.linalg.norm(noise)
        v = correlation * base + np.sqrt(max(0, 1 - correlation**2)) * noise
        p = v.reshape(N, D)
        norms = np.linalg.norm(p, axis=1, keepdims=True)
        p = p / np.maximum(norms, 1e-12)
        patterns.append(p)

    return patterns


def pattern_similarity_matrix(patterns: List[np.ndarray]) -> np.ndarray:
    """Compute pairwise Frobenius similarity: S_kl = Σ_i (p_k^i · p_l^i)."""
    P = len(patterns)
    S = np.zeros((P, P))
    for k in range(P):
        for l in range(k, P):
            s = np.sum(patterns[k] * patterns[l])
            S[k, l] = s
            S[l, k] = s
    return S


# =============================================================================
# EXPERIMENT G: CORRELATED PATTERN RECALL
# =============================================================================

def experiment_G_correlation(cfg: Phase3Config, seed: int = 42) -> Dict:
    """
    H1: Does recall survive correlated patterns?

    For each correlation level, generate P patterns, store them,
    and measure faithful recall rate + Gram condition number.

    Pass: faithful recall ≥ 80% at correlation ≤ 0.3
    Fail: recall collapses at any non-trivial correlation
    """
    print("\n" + "=" * 72)
    print("EXPERIMENT G: Correlated Pattern Recall")
    print("=" * 72)
    print(f"  N={cfg.g_n_units}, D={cfg.pattern_dim}, P={cfg.g_pattern_count}")
    print(f"  Corruption={cfg.g_corruption:.0%}, Trials={cfg.g_n_trials}")
    print(f"  Correlation levels: {cfg.g_correlation_levels}\n")

    results = {}

    for corr in cfg.g_correlation_levels:
        rng = np.random.RandomState(seed + int(corr * 1000))
        patterns = make_correlated_patterns(
            cfg.g_pattern_count, cfg.g_n_units, cfg.pattern_dim, corr, rng
        )

        # Diagnostics: pattern similarity and Gram conditioning
        sim_mat = pattern_similarity_matrix(patterns)
        off_diag = sim_mat[np.triu_indices(len(patterns), k=1)]
        mean_cross_sim = float(np.mean(np.abs(off_diag)))

        net = TangentTOLS(
            n_units=cfg.g_n_units,
            pattern_dim=cfg.pattern_dim,
            coupling_strength=cfg.base_K,
            dt=cfg.dt,
            coupling_rule="tensor_pseudo",
            adaptive_K=True,
            seed=seed,
        )
        for p in patterns:
            net.store_pattern(p)

        gram_cond = float(np.linalg.cond(net.G)) if net.G is not None else 0.0

        faithful = 0
        classified = 0
        total = 0
        sims = []

        for pi, target in enumerate(patterns):
            for trial in range(cfg.g_n_trials):
                trial_rng = np.random.RandomState(seed + pi * 50000 + trial + int(corr * 1e6))
                cue = corrupt(target, cfg.g_corruption, trial_rng)
                recalled, _, _ = net.recall(
                    cue, max_steps=cfg.max_steps, tol=cfg.convergence_tol, log=False
                )

                # Classification
                pattern_sims = [net.pattern_similarity(recalled, q) for q in patterns]
                best_idx = int(np.argmax(pattern_sims))
                if best_idx == pi:
                    classified += 1

                # Faithful recall
                target_sim = pattern_sims[pi]
                sims.append(target_sim)
                if target_sim >= cfg.faithful_threshold:
                    faithful += 1
                total += 1

        clf_rate = classified / total
        faithful_rate = faithful / total
        mean_sim = float(np.mean(sims))

        results[corr] = {
            "clf_rate": clf_rate,
            "faithful_rate": faithful_rate,
            "mean_sim": mean_sim,
            "gram_cond": gram_cond,
            "mean_cross_sim": mean_cross_sim,
        }

        print(
            f"  ρ={corr:.1f}: clf={clf_rate:.3f}  faithful={faithful_rate:.3f}  "
            f"sim={mean_sim:.3f}  κ(G)={gram_cond:.1e}  cross_sim={mean_cross_sim:.3f}"
        )

    # Verdict
    print("\n  --- H1 VERDICT ---")
    # Pass if faithful recall ≥ 0.80 for correlation ≤ 0.3
    low_corr_pass = all(
        results[c]["faithful_rate"] >= 0.80
        for c in cfg.g_correlation_levels if c <= 0.3
    )
    # Find the correlation where recall first drops below 0.80
    failure_corr = None
    for c in sorted(cfg.g_correlation_levels):
        if results[c]["faithful_rate"] < 0.80:
            failure_corr = c
            break

    if low_corr_pass:
        print(f"  PASS: Faithful recall ≥ 80% for ρ ≤ 0.3")
        if failure_corr:
            print(f"  Degradation onset at ρ={failure_corr:.1f}")
        else:
            print(f"  No degradation detected up to ρ={max(cfg.g_correlation_levels):.1f}")
    else:
        print(f"  FAIL: Recall collapses at low correlation. Orthogonal-only illusion confirmed.")

    return results


# =============================================================================
# EXPERIMENT H: POST-CONVERGENCE STABILITY (PHANTOM BASIN TEST)
# =============================================================================

def experiment_H_stability(cfg: Phase3Config, seed: int = 42) -> Dict:
    """
    H2: Are recalled states genuinely stable, or metastable transients?

    Protocol:
      1. Recall from corrupted cue → converged state S*.
      2. Perturb S* by small noise (5% of units replaced).
      3. Re-run dynamics for 500 more steps.
      4. Measure similarity between re-converged state and S*.

    If S* is a true fixed point, the perturbed state returns to S*.
    If S* is metastable, the perturbed state drifts to a different state.

    Pass: sim(re-converged, S*) ≥ 0.99 for ≥ 90% of trials
    Fail: S* is not recovered, indicating phantom basins
    """
    print("\n" + "=" * 72)
    print("EXPERIMENT H: Post-Convergence Stability (Phantom Basin Test)")
    print("=" * 72)
    print(f"  N={cfg.h_n_units}, P={cfg.h_pattern_count}")
    print(f"  Perturbation magnitude: {cfg.h_perturbation_magnitude:.0%} of units")
    print(f"  Post-convergence steps: {cfg.h_post_convergence_steps}")
    print(f"  Trials: {cfg.h_n_trials}\n")

    rng = np.random.RandomState(seed)
    patterns = make_orthogonal_patterns(
        cfg.h_pattern_count, cfg.h_n_units, cfg.pattern_dim, rng
    )

    net = TangentTOLS(
        n_units=cfg.h_n_units,
        pattern_dim=cfg.pattern_dim,
        coupling_strength=cfg.base_K,
        dt=cfg.dt,
        coupling_rule="tensor_pseudo",
        adaptive_K=True,
        seed=seed,
    )
    for p in patterns:
        net.store_pattern(p)

    stable_count = 0
    total = 0
    return_sims = []
    target_preserved = []

    for pi, target in enumerate(patterns):
        for trial in range(cfg.h_n_trials):
            trial_rng = np.random.RandomState(seed + pi * 10000 + trial)

            # Step 1: Recall from corrupted cue
            cue = corrupt(target, 0.20, trial_rng)
            recalled_star, steps1, diag1 = net.recall(
                cue, max_steps=cfg.max_steps, tol=cfg.convergence_tol, log=False
            )

            # Check we actually recalled the target
            sim_to_target = net.pattern_similarity(recalled_star, target)
            if sim_to_target < cfg.faithful_threshold:
                # Didn't recall target — skip (this tests stability, not recall)
                continue

            # Step 2: Perturb the converged state
            perturbed = corrupt(recalled_star, cfg.h_perturbation_magnitude, trial_rng)

            # Step 3: Re-run dynamics
            re_recalled, steps2, diag2 = net.recall(
                perturbed, max_steps=cfg.h_post_convergence_steps,
                tol=cfg.convergence_tol, log=False
            )

            # Step 4: Measure return similarity
            return_sim = net.pattern_similarity(re_recalled, recalled_star)
            target_sim_after = net.pattern_similarity(re_recalled, target)

            return_sims.append(return_sim)
            target_preserved.append(target_sim_after >= cfg.faithful_threshold)

            if return_sim >= cfg.h_stability_threshold:
                stable_count += 1
            total += 1

    if total == 0:
        print("  ERROR: No successful recalls to test stability on.")
        return {"pass": False, "total": 0}

    stability_rate = stable_count / total
    mean_return_sim = float(np.mean(return_sims))
    target_preservation_rate = sum(target_preserved) / len(target_preserved)

    print(f"  Valid trials:         {total}")
    print(f"  Stability rate:       {stability_rate:.3f} (threshold: ≥ 0.90)")
    print(f"  Mean return sim:      {mean_return_sim:.4f}")
    print(f"  Target preservation:  {target_preservation_rate:.3f}")

    passed = stability_rate >= 0.90
    print(f"\n  --- H2 VERDICT ---")
    if passed:
        print(f"  PASS: Recalled states are genuinely stable fixed points.")
    else:
        print(f"  FAIL: {1.0 - stability_rate:.0%} of recalled states are phantom basins.")
        print(f"  Convergence check is catching transients, not attractors.")

    return {
        "stability_rate": stability_rate,
        "mean_return_sim": mean_return_sim,
        "target_preservation_rate": target_preservation_rate,
        "total_trials": total,
        "pass": passed,
    }


# =============================================================================
# EXPERIMENT I: SCALE-UP
# =============================================================================

def experiment_I_scale(cfg: Phase3Config, seed: int = 42) -> Dict:
    """
    H3: Does the architecture work beyond N=32?

    For N in {32, 64, 128}, test recall at loading ratios α = P/N.
    Track faithful recall rate and Gram condition number.

    Pass: faithful recall ≥ 80% at α=0.5 for all N values
    Fail: recall degrades with N at fixed α (architecture doesn't scale)
    """
    print("\n" + "=" * 72)
    print("EXPERIMENT I: Scale-Up Test")
    print("=" * 72)
    print(f"  N values: {cfg.i_n_values}")
    print(f"  Loading ratios α: {cfg.i_loading_ratios}")
    print(f"  Corruption: {cfg.i_corruption:.0%}, Trials: {cfg.i_n_trials}\n")

    results = {}

    for N in cfg.i_n_values:
        results[N] = {}
        for alpha in cfg.i_loading_ratios:
            P = max(1, int(N * alpha))
            rng = np.random.RandomState(seed + N + int(alpha * 1000))

            patterns = make_orthogonal_patterns(P, N, cfg.pattern_dim, rng)

            net = TangentTOLS(
                n_units=N,
                pattern_dim=cfg.pattern_dim,
                coupling_strength=cfg.base_K,
                dt=cfg.dt,
                coupling_rule="tensor_pseudo",
                adaptive_K=True,
                seed=seed,
            )
            for p in patterns:
                net.store_pattern(p)

            gram_cond = float(np.linalg.cond(net.G)) if net.G is not None else 0.0

            faithful = 0
            total = 0
            sims_list = []

            for pi, target in enumerate(patterns):
                for trial in range(cfg.i_n_trials):
                    trial_rng = np.random.RandomState(seed + N * 1000 + pi * 100 + trial)
                    cue = corrupt(target, cfg.i_corruption, trial_rng)
                    recalled, _, _ = net.recall(
                        cue, max_steps=cfg.max_steps, tol=cfg.convergence_tol, log=False
                    )
                    sim = net.pattern_similarity(recalled, target)
                    sims_list.append(sim)
                    if sim >= cfg.faithful_threshold:
                        faithful += 1
                    total += 1

            faithful_rate = faithful / total if total > 0 else 0
            mean_sim = float(np.mean(sims_list)) if sims_list else 0

            results[N][alpha] = {
                "P": P,
                "faithful_rate": faithful_rate,
                "mean_sim": mean_sim,
                "gram_cond": gram_cond,
                "total_trials": total,
            }

            print(
                f"  N={N:3d}, α={alpha:.2f} (P={P:3d}): "
                f"faithful={faithful_rate:.3f}  sim={mean_sim:.3f}  κ(G)={gram_cond:.1e}"
            )

    # Verdict: does faithful recall at α=0.5 hold across N?
    print(f"\n  --- H3 VERDICT ---")
    half_load_results = {}
    for N in cfg.i_n_values:
        if 0.5 in results[N]:
            half_load_results[N] = results[N][0.5]["faithful_rate"]

    if half_load_results:
        all_pass = all(r >= 0.80 for r in half_load_results.values())
        degrading = False
        prev_rate = None
        for N in sorted(half_load_results.keys()):
            rate = half_load_results[N]
            if prev_rate is not None and rate < prev_rate - 0.10:
                degrading = True
            prev_rate = rate

        if all_pass and not degrading:
            print(f"  PASS: Faithful recall ≥ 80% at α=0.5 for all N.")
        elif all_pass and degrading:
            print(f"  WARNING: Recall passes but is degrading with N. May fail at larger scale.")
        else:
            failing_N = [N for N, r in half_load_results.items() if r < 0.80]
            print(f"  FAIL: Recall drops below 80% at N={failing_N}.")
    else:
        print(f"  INCONCLUSIVE: α=0.5 not tested.")

    return results


# =============================================================================
# MAIN: PHASE 3 REPORT
# =============================================================================

def run_phase3(seed: int = 42):
    cfg = Phase3Config()

    print("=" * 72)
    print("TOLS v3 — PHASE 3: ADVERSARIAL STRESS TEST")
    print("V0 Falsification Testbed | APEX Core 4.3")
    print("=" * 72)

    t0 = time.time()

    # Experiment G: Correlated patterns
    exp_g = experiment_G_correlation(cfg, seed)

    # Experiment H: Phantom basin test
    exp_h = experiment_H_stability(cfg, seed)

    # Experiment I: Scale-up
    exp_i = experiment_I_scale(cfg, seed)

    elapsed = time.time() - t0

    # FINAL VERDICT
    print("\n" + "=" * 72)
    print("PHASE 3 FINAL VERDICT")
    print("=" * 72)

    # H1: Correlation robustness
    h1_pass = all(
        exp_g[c]["faithful_rate"] >= 0.80
        for c in cfg.g_correlation_levels if c <= 0.3
    )
    # Find max survivable correlation
    max_corr = 0.0
    for c in sorted(cfg.g_correlation_levels):
        if exp_g[c]["faithful_rate"] >= 0.80:
            max_corr = c

    # H2: Stability
    h2_pass = exp_h.get("pass", False)

    # H3: Scale
    h3_pass_half = True
    for N in cfg.i_n_values:
        if 0.5 in exp_i.get(N, {}):
            if exp_i[N][0.5]["faithful_rate"] < 0.80:
                h3_pass_half = False

    print(f"\n  H1 (Correlation robustness):  {'PASS' if h1_pass else 'FAIL'}")
    print(f"      Max survivable ρ:          {max_corr:.1f}")
    print(f"  H2 (Basin stability):          {'PASS' if h2_pass else 'FAIL'}")
    if exp_h.get("total_trials", 0) > 0:
        print(f"      Stability rate:            {exp_h['stability_rate']:.3f}")
    print(f"  H3 (Scale-up):                 {'PASS' if h3_pass_half else 'FAIL'}")

    all_pass = h1_pass and h2_pass and h3_pass_half

    if all_pass:
        decision = "VALIDATED"
        detail = (
            "The tensor pseudoinverse architecture survives correlated patterns, "
            "produces genuinely stable fixed points, and scales beyond N=32. "
            "The associative memory hypothesis is supported."
        )
    elif h2_pass and (h1_pass or h3_pass_half):
        decision = "CONDITIONAL PASS"
        detail = (
            "The architecture is stable and partially robust. "
            f"{'Correlation sensitivity needs attention. ' if not h1_pass else ''}"
            f"{'Scale degradation detected. ' if not h3_pass_half else ''}"
            "Further iteration recommended before declaring validated."
        )
    else:
        decision = "REDESIGN"
        issues = []
        if not h1_pass:
            issues.append("orthogonal-only illusion confirmed")
        if not h2_pass:
            issues.append("phantom basins detected")
        if not h3_pass_half:
            issues.append("scale collapse")
        detail = f"Critical failures: {', '.join(issues)}."

    print(f"\n  DECISION: {decision}")
    print(f"  {detail}")
    print(f"\n  Elapsed: {elapsed:.1f}s")

    return {
        "h1_pass": h1_pass,
        "h2_pass": h2_pass,
        "h3_pass": h3_pass_half,
        "max_survivable_correlation": max_corr,
        "decision": decision,
        "exp_g": exp_g,
        "exp_h": exp_h,
        "exp_i": exp_i,
    }


if __name__ == "__main__":
    run_phase3(seed=42)

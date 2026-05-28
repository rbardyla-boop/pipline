"""
STEP 1: K_EFF ABLATION
Question: Is the capacity cliff at P≈56 caused by adaptive K_eff dropping
too low, or by geometric basin shrinkage?

VERDICT logic:
  If P_max differs across conditions → K_EFF IS THE BOTTLENECK
  If P_max is the same regardless of K → GEOMETRIC LIMIT CONFIRMED
"""

import numpy as np
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tols_v3_phase2 import TangentTOLS, make_orthogonal_patterns, corrupt

N, D = 32, 8
CORRUPTION = 0.15
N_TRIALS = 10
MAX_PATTERNS_TESTED = 8   # cap per P for speed
P_SWEEP = (4, 8, 16, 24, 32, 40, 48, 56, 64)
MAX_STEPS = 1000
TOL = 1e-5
FAITHFUL_THR = 0.95
PASS_THR = 0.80

CONDITIONS = [
    ("A: adaptive K=4",   True,  4.0),
    ("B: fixed  K=4",     False, 4.0),
    ("C: fixed  K=8",     False, 8.0),
    ("D: fixed  K=16",    False, 16.0),
]


def faithful_rate_at_P(P, adaptive_K, base_K, seed=42):
    rng = np.random.RandomState(seed + P)
    try:
        patterns = make_orthogonal_patterns(P, N, D, rng)
    except ValueError as e:
        return 0.0, f"SKIP:{e}"

    net = TangentTOLS(
        n_units=N, pattern_dim=D, coupling_strength=base_K,
        dt=0.005, coupling_rule="tensor_pseudo",
        adaptive_K=adaptive_K, seed=seed,
    )
    for p in patterns:
        net.store_pattern(p)

    faithful = 0
    total = 0
    n_test = min(P, MAX_PATTERNS_TESTED)
    for pi in range(n_test):
        target = patterns[pi]
        for trial in range(N_TRIALS):
            tr = np.random.RandomState(seed + P * 10000 + pi * 100 + trial)
            cue = corrupt(target, CORRUPTION, tr)
            try:
                recalled, _, _ = net.recall(cue, max_steps=MAX_STEPS, tol=TOL, log=False)
                sim = net.pattern_similarity(recalled, target)
                if sim >= FAITHFUL_THR:
                    faithful += 1
            except np.linalg.LinAlgError as e:
                print(f"  LinAlgError P={P} pi={pi} trial={trial}: {e}")
            total += 1

    return faithful / total if total > 0 else 0.0, "OK"


def k_eff(adaptive_K, base_K, P):
    return base_K * N / P if adaptive_K else base_K


print("=" * 72)
print("STEP 1: K_EFF ABLATION")
print("=" * 72)
print(f"N={N}, D={D}, corruption={CORRUPTION:.0%}, trials={N_TRIALS}/pattern (cap {MAX_PATTERNS_TESTED})\n")

t0 = time.time()

# Matrix: conditions × P values
results = {}
for label, adaptive_K, base_K in CONDITIONS:
    results[label] = {}
    for P in P_SWEEP:
        rate, status = faithful_rate_at_P(P, adaptive_K, base_K, seed=42)
        results[label][P] = rate

# Print full table
header = f"  {'Condition':<22}" + "".join(f"  P={p:<4}" for p in P_SWEEP)
print(header)
print("  " + "-" * (len(header) - 2))

for label, adaptive_K, base_K in CONDITIONS:
    row = f"  {label:<22}"
    for P in P_SWEEP:
        r = results[label][P]
        row += f"  {r:5.2f} "
    print(row)

# P_max for each condition
print()
print(f"  {'Condition':<22}  {'K_eff@P=56':>12}  {'P_max':>8}  {'α_max':>8}")
print("  " + "-" * 58)

pmax_values = []
for label, adaptive_K, base_K in CONDITIONS:
    keff56 = k_eff(adaptive_K, base_K, 56)
    pmax = 0
    for P in P_SWEEP:
        if results[label][P] >= PASS_THR:
            pmax = P
    alpha = pmax / N
    pmax_values.append(pmax)
    print(f"  {label:<22}  {keff56:>12.2f}  {pmax:>8}  {alpha:>8.3f}")

# Verdict
unique_pmaxes = set(pmax_values)
spread = max(pmax_values) - min(pmax_values)
print()
if spread >= 8:   # at least one P step difference
    verdict = "K_EFF IS THE BOTTLENECK"
    detail = f"P_max range: {min(pmax_values)}..{max(pmax_values)} (spread={spread}). Higher K pushes capacity."
else:
    verdict = "GEOMETRIC LIMIT CONFIRMED"
    detail = f"P_max range: {min(pmax_values)}..{max(pmax_values)} (spread={spread}). K does not move the cliff."

print(f"  VERDICT: {verdict}")
print(f"  {detail}")
print(f"\n  Elapsed: {time.time()-t0:.1f}s")

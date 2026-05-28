"""
STEP 2: BASIN RADIUS VS P
Question: Do attractor basins shrink as patterns are added?

VERDICT logic:
  If basin_radius decreases monotonically → BASIN COMPRESSION CONFIRMED
  If basin_radius is flat but recall fails  → DYNAMICS TOO SLOW, NOT BASINS
"""

import numpy as np
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tols_v3_phase2 import TangentTOLS, make_orthogonal_patterns, corrupt

N, D = 32, 8
BASE_K = 4.0
N_TRIALS = 20
MAX_STEPS = 1000
TOL = 1e-5
FAITHFUL_THR = 0.95
PASS_THR = 0.80

P_VALUES = (1, 4, 8, 16, 24, 32, 48)
CORRUPTION_SWEEP = tuple(round(c, 2) for c in np.arange(0.05, 0.95, 0.05))


def k_eff(P):
    return BASE_K * N / P


def basin_test(P, seed=42):
    rng = np.random.RandomState(seed + P)
    try:
        patterns = make_orthogonal_patterns(P, N, D, rng)
    except ValueError as e:
        return None, f"SKIP:{e}"

    net = TangentTOLS(
        n_units=N, pattern_dim=D, coupling_strength=BASE_K,
        dt=0.005, coupling_rule="tensor_pseudo",
        adaptive_K=True, seed=seed,
    )
    for p in patterns:
        net.store_pattern(p)

    # Test against the first stored pattern only (all are equivalent by symmetry)
    target = patterns[0]
    basin_radius = 0.0

    for corr in CORRUPTION_SWEEP:
        faithful = 0
        for trial in range(N_TRIALS):
            tr = np.random.RandomState(seed + P * 100000 + int(corr * 1000) * 100 + trial)
            cue = corrupt(target, corr, tr)
            try:
                recalled, _, _ = net.recall(cue, max_steps=MAX_STEPS, tol=TOL, log=False)
                sim = net.pattern_similarity(recalled, target)
                if sim >= FAITHFUL_THR:
                    faithful += 1
            except np.linalg.LinAlgError as e:
                print(f"  LinAlgError P={P} corr={corr:.2f}: {e}")
        rate = faithful / N_TRIALS
        if rate >= PASS_THR:
            basin_radius = corr   # keep updating: max where pass ≥ 0.80

    return basin_radius, "OK"


print("=" * 72)
print("STEP 2: BASIN RADIUS VS P")
print("=" * 72)
print(f"N={N}, D={D}, base_K={BASE_K}, adaptive_K=True")
print(f"Corruption sweep: {CORRUPTION_SWEEP[0]:.2f}..{CORRUPTION_SWEEP[-1]:.2f} "
      f"(step 0.05), {N_TRIALS} trials/level\n")

t0 = time.time()

rows = []
for P in P_VALUES:
    radius, status = basin_test(P, seed=42)
    ke = k_eff(P)
    rows.append((P, radius, ke, status))
    flag = f"  ← {status}" if status != "OK" else ""
    r_str = f"{radius:.2f}" if radius is not None else " N/A"
    print(f"  P={P:>3}: basin_radius={r_str}  K_eff={ke:6.2f}{flag}")

# Monotonicity check
valid_rows = [(P, r, k) for P, r, k, s in rows if r is not None and s == "OK"]
print()

if len(valid_rows) >= 2:
    radii = [r for _, r, _ in valid_rows]
    ps = [P for P, _, _ in valid_rows]

    # Count monotone decreases
    decreases = sum(1 for i in range(1, len(radii)) if radii[i] < radii[i-1])
    total_pairs = len(radii) - 1
    mono_fraction = decreases / total_pairs if total_pairs > 0 else 0

    # Check if basin_radius at high P is meaningfully smaller
    first_r = radii[0]
    last_r = radii[-1]
    drop = first_r - last_r

    print(f"  First basin_radius (P={ps[0]}): {first_r:.2f}")
    print(f"  Last  basin_radius (P={ps[-1]}): {last_r:.2f}")
    print(f"  Drop: {drop:.2f}")
    print(f"  Monotone-decrease pairs: {decreases}/{total_pairs}")

    if mono_fraction >= 0.6 and drop > 0.10:
        verdict = "BASIN COMPRESSION CONFIRMED"
        detail = f"Basin radius drops from {first_r:.2f} to {last_r:.2f} as P grows."
    elif drop <= 0.05:
        verdict = "DYNAMICS TOO SLOW, NOT BASINS"
        detail = f"Basin radius is flat ({first_r:.2f}→{last_r:.2f}). Recall fails for another reason."
    else:
        verdict = "PARTIAL COMPRESSION"
        detail = f"Non-monotone drop {first_r:.2f}→{last_r:.2f}, {mono_fraction:.0%} monotone."
else:
    verdict = "INCONCLUSIVE"
    detail = "Insufficient valid data points."

print(f"\n  VERDICT: {verdict}")
print(f"  {detail}")
print(f"\n  Elapsed: {time.time()-t0:.1f}s")

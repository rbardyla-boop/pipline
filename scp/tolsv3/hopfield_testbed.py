"""
Classical Hopfield testbed: binary patterns, Hebbian coupling.
Four criteria: capacity, basin radius, energy monotonicity, κ(G) vs accuracy.
N=100, P varied. ~50 lines of numpy.
"""
import numpy as np

N = 100
N_TRIALS = 50
CORRUPT_RATES = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40]
MAX_STEPS = 50
FAITHFUL_THR = 0.95   # fraction of bits correct
PASS_THR = 0.80

def make_patterns(P, rng):
    return rng.choice([-1, 1], size=(P, N)).astype(float)

def hebbian(patterns):
    P, N = patterns.shape
    W = patterns.T @ patterns / N
    np.fill_diagonal(W, 0)
    return W

def update(state, W):
    return np.sign(W @ state)

def recall(cue, W, steps=MAX_STEPS):
    s = cue.copy()
    for _ in range(steps):
        s_new = update(s, W)
        if np.array_equal(s_new, s): break
        s = s_new
    return s

def similarity(a, b):
    return float(np.mean(a == b))

def energy(s, W):
    return -0.5 * s @ W @ s

def corrupt_binary(pattern, rate, rng):
    c = pattern.copy()
    n_flip = max(1, int(N * rate))
    idx = rng.choice(N, size=n_flip, replace=False)
    c[idx] *= -1
    return c

# --- Criterion 1: Capacity (P_max where faithful recall >= 80%) ---
print("=" * 60)
print("CLASSICAL HOPFIELD TESTBED (N=100, Hebbian, binary)")
print("=" * 60)

print("\n[1] Capacity sweep (corruption=0.15, 50 trials per P)")
print(f"  {'P':>4}  {'alpha':>6}  {'faithful':>10}  {'kappa':>8}")
p_max = 0
for P in [2, 4, 8, 10, 12, 14, 16, 18, 20, 25, 30]:
    rng = np.random.RandomState(42 + P)
    patterns = make_patterns(P, rng)
    W = hebbian(patterns)
    G = patterns @ patterns.T / N
    kappa = float(np.linalg.cond(G))
    faithful = 0
    for trial in range(N_TRIALS):
        tr = np.random.RandomState(1000 + P*100 + trial)
        pi = trial % P
        cue = corrupt_binary(patterns[pi], 0.15, tr)
        rec = recall(cue, W)
        if similarity(rec, patterns[pi]) >= FAITHFUL_THR:
            faithful += 1
    rate_f = faithful / N_TRIALS
    if rate_f >= PASS_THR: p_max = P
    print(f"  {P:>4}  {P/N:>6.3f}  {rate_f:>10.3f}  {kappa:>8.2f}")

print(f"\n  P_max = {p_max}  (alpha_max = {p_max/N:.3f})")
print(f"  Theory: 0.138*N = {0.138*N:.1f}")

# --- Criterion 2: Basin radius vs P ---
print("\n[2] Basin radius vs P (faithful >= 80% over corruption sweep)")
for P in [4, 8, 12, 16]:
    rng = np.random.RandomState(42 + P)
    patterns = make_patterns(P, rng)
    W = hebbian(patterns)
    basin = 0.0
    for rate in CORRUPT_RATES:
        faithful = 0
        for trial in range(N_TRIALS):
            tr = np.random.RandomState(2000 + P*100 + int(rate*1000) + trial)
            cue = corrupt_binary(patterns[0], rate, tr)
            rec = recall(cue, W)
            if similarity(rec, patterns[0]) >= FAITHFUL_THR:
                faithful += 1
        if faithful / N_TRIALS >= PASS_THR:
            basin = rate
    print(f"  P={P:>2}  basin_radius={basin:.2f}")

# --- Criterion 3: Energy monotonicity (Lyapunov check) ---
print("\n[3] Energy monotonicity (10 random recalls, P=10)")
rng = np.random.RandomState(42)
patterns = make_patterns(10, rng)
W = hebbian(patterns)
violations = 0; total_steps = 0
for trial in range(10):
    tr = np.random.RandomState(3000 + trial)
    cue = corrupt_binary(patterns[0], 0.20, tr)
    s = cue.copy()
    E_prev = energy(s, W)
    for step in range(MAX_STEPS):
        s_new = update(s, W)
        E_new = energy(s_new, W)
        if E_new > E_prev + 1e-10:
            violations += 1
        E_prev = E_new
        total_steps += 1
        if np.array_equal(s_new, s): break
        s = s_new
print(f"  Energy violations: {violations}/{total_steps} steps")
print(f"  {'PASS' if violations == 0 else 'FAIL'} — Lyapunov guarantee {'holds' if violations==0 else 'violated'}")

# --- Criterion 4: κ(G) vs accuracy across P ---
print("\n[4] κ(G) vs accuracy at fixed corruption=0.25")
print(f"  {'P':>4}  {'kappa':>8}  {'accuracy':>10}")
for P in [4, 8, 12, 14, 16, 18]:
    rng = np.random.RandomState(42 + P)
    patterns = make_patterns(P, rng)
    W = hebbian(patterns)
    G = patterns @ patterns.T / N
    kappa = float(np.linalg.cond(G))
    correct = 0
    for trial in range(N_TRIALS):
        tr = np.random.RandomState(4000 + P*100 + trial)
        pi = trial % P
        cue = corrupt_binary(patterns[pi], 0.25, tr)
        rec = recall(cue, W)
        if similarity(rec, patterns[pi]) >= FAITHFUL_THR:
            correct += 1
    print(f"  {P:>4}  {kappa:>8.2f}  {correct/N_TRIALS:>10.3f}")

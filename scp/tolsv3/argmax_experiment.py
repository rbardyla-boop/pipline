"""Argmax baseline: does G^{-1}·ovl argmax match full dynamics?"""
import numpy as np, sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tols_v3_phase2 import TangentTOLS

N, D, P = 32, 8, 10
BLOCK_RATE, NOISE_SIGMA, CROSS_RATE = 0.25, 0.3, 0.30
N_TRIALS = 20
THRESH_NOTHING, THRESH_VALUE = 0.02, 0.10

def normalize_rows(M):
    return M / np.maximum(np.linalg.norm(M, axis=1, keepdims=True), 1e-12)

# Load MNIST prototypes
try:
    from sklearn.datasets import fetch_openml
    mnist = fetch_openml("mnist_784", version=1, as_frame=False, parser="liac-arff", cache=True)
    X = mnist.data.astype(np.float32); y = mnist.target.astype(int)
    protos = []
    for cls in range(P):
        idx = np.where(y == cls)[0]
        mean_img = X[idx].mean(axis=0)
        factor = len(mean_img) // (N * D)
        pooled = mean_img[:N*D*factor].reshape(N*D, factor).mean(axis=1)
        p = pooled.reshape(N, D)
        p += np.random.RandomState(cls).randn(*p.shape) * 0.001
        protos.append(normalize_rows(p))
    print("MNIST loaded")
except Exception as e:
    print(f"MNIST failed ({e}), using synthetic")
    rng = np.random.RandomState(99)
    protos = []
    for cls in range(P):
        v = rng.randn(N*D)*0.2; v[cls*(N*D//P):(cls+1)*(N*D//P)] += rng.randn(N*D//P)*2
        p = normalize_rows(v.reshape(N, D)); protos.append(p)

net = TangentTOLS(n_units=N, pattern_dim=D, coupling_strength=4.0,
                  dt=0.005, coupling_rule="tensor_pseudo", adaptive_K=True, seed=42)
for p in protos: net.store_pattern(p)

PM = np.array([p.flatten() for p in protos])   # (P, N*D)
G = net.G
G_inv = net.G_inv

def argmax_predict(cue):
    ovl = PM @ cue.flatten()           # G^{-1}·ovl argmax
    alpha = G_inv @ ovl
    return int(np.argmax(alpha))

def dynamics_predict(cue):
    recalled, _, _ = net.recall(cue, max_steps=1000, tol=1e-5, log=False)
    sims = [net.pattern_similarity(recalled, p) for p in protos]
    return int(np.argmax(sims))

def block_cue(target, rng):
    c = target.copy()
    for i in range(max(1, int(N*BLOCK_RATE))):
        v = rng.randn(D); c[i] = v/np.linalg.norm(v)
    return c

def gauss_cue(target, rng):
    return normalize_rows(target + rng.randn(*target.shape)*NOISE_SIGMA)

def cross_cue(target, distractor):
    return normalize_rows((1-CROSS_RATE)*target + CROSS_RATE*distractor)

print(f"\nκ(G) = {np.linalg.cond(G):.1f}")
print(f"\n{'Corruption':<10} {'Argmax':>8} {'Dynamics':>10} {'Gap':>8} {'Verdict'}")
print("-"*52)

results = {}
for corr_type in ["block", "gauss", "cross"]:
    ax_correct, dyn_correct = 0, 0
    for cls in range(P):
        target = protos[cls]
        overlaps = [float(np.sum(target*protos[j])) if j!=cls else -1e9 for j in range(P)]
        distractor = protos[int(np.argmax(overlaps))]
        for trial in range(N_TRIALS):
            rng = np.random.RandomState(42 + cls*10000 + trial)
            if corr_type == "block":    cue = block_cue(target, rng)
            elif corr_type == "gauss":  cue = gauss_cue(target, rng)
            else:                        cue = cross_cue(target, distractor)
            ax_pred = argmax_predict(cue)
            try:   dyn_pred = dynamics_predict(cue)
            except: dyn_pred = -1
            if ax_pred == cls:  ax_correct += 1
            if dyn_pred == cls: dyn_correct += 1

    total = P * N_TRIALS
    ax_acc  = ax_correct  / total
    dyn_acc = dyn_correct / total
    gap = abs(ax_acc - dyn_acc)
    if   gap < THRESH_NOTHING: verdict = "DYNAMICS ADD NOTHING"
    elif gap > THRESH_VALUE:   verdict = "DYNAMICS ADD VALUE"
    else:                       verdict = "MARGINAL"
    results[corr_type] = (ax_acc, dyn_acc, gap, verdict)
    print(f"{corr_type:<10} {ax_acc:>8.3f} {dyn_acc:>10.3f} {gap:>8.3f}  {verdict}")

print()
verdicts = [v for _,_,_,v in results.values()]
if all(v == "DYNAMICS ADD NOTHING" for v in verdicts):
    print("FINAL VERDICT: DYNAMICS ADD NOTHING")
elif any(v == "DYNAMICS ADD VALUE" for v in verdicts):
    print("FINAL VERDICT: DYNAMICS ADD VALUE")
else:
    print("FINAL VERDICT: MARGINAL")

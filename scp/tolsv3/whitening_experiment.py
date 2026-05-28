"""Whitening test: G^{-1/2} on MNIST prototypes, κ reduction, block accuracy."""
import numpy as np, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tols_v3_phase2 import TangentTOLS

N, D, P = 32, 8, 10
BLOCK_RATE = 0.25
N_TRIALS = 20
KAPPA_GATE = 40
KAPPA_TIGHT = 15
ACC_PASS = 0.85

def normalize_rows(M):
    return M / np.maximum(np.linalg.norm(M, axis=1, keepdims=True), 1e-12)

# Load MNIST prototypes (identical to argmax_experiment)
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
    print(f"MNIST failed ({e}), synthetic")
    rng = np.random.RandomState(99)
    protos = []
    for cls in range(P):
        v = rng.randn(N*D)*0.2; v[cls*(N*D//P):(cls+1)*(N*D//P)] += rng.randn(N*D//P)*2
        protos.append(normalize_rows(v.reshape(N, D)))

PM = np.array([p.flatten() for p in protos])       # (P, N*D)
G = PM @ PM.T
kappa_before = float(np.linalg.cond(G))
print(f"κ(G) before whitening: {kappa_before:.1f}")

# --- Whitening ---
eigvals, eigvecs = np.linalg.eigh(G)               # G = V Λ V^T
eigvals_safe = np.maximum(eigvals, 1e-10)
G_invsqrt = eigvecs @ np.diag(1.0/np.sqrt(eigvals_safe)) @ eigvecs.T   # (P, P)

PM_white = G_invsqrt @ PM                          # (P, N*D) — whitened flat patterns

# Re-normalize each unit block D→S^{D-1}
PM_white_renorm = PM_white.copy()
for k in range(P):
    row = PM_white[k].reshape(N, D)
    row = normalize_rows(row)
    PM_white_renorm[k] = row.flatten()

protos_white = [PM_white_renorm[k].reshape(N, D) for k in range(P)]

G_prime = PM_white_renorm @ PM_white_renorm.T
kappa_after = float(np.linalg.cond(G_prime))
print(f"κ(G') after whitening+renorm: {kappa_after:.1f}")

if kappa_after > KAPPA_GATE:
    print(f"\nVERDICT: SPHERE CONSTRAINT DEFEATS WHITENING (κ'={kappa_after:.1f} > {KAPPA_GATE})")
    sys.exit(0)

# --- Block occlusion with whitened patterns ---
net = TangentTOLS(n_units=N, pattern_dim=D, coupling_strength=4.0,
                  dt=0.005, coupling_rule="tensor_pseudo", adaptive_K=True, seed=42)
for p in protos_white: net.store_pattern(p)

PM_w = np.array([p.flatten() for p in protos_white])

def block_cue(target, rng):
    c = target.copy()
    for i in range(max(1, int(N*BLOCK_RATE))):
        v = rng.randn(D); c[i] = v/np.linalg.norm(v)
    return c

correct, total = 0, 0
for cls in range(P):
    target = protos_white[cls]
    for trial in range(N_TRIALS):
        rng = np.random.RandomState(42 + cls*10000 + trial)
        cue = block_cue(target, rng)
        try:
            recalled, _, _ = net.recall(cue, max_steps=1000, tol=1e-5, log=False)
            sims = [net.pattern_similarity(recalled, p) for p in protos_white]
            if int(np.argmax(sims)) == cls: correct += 1
        except: pass
        total += 1

acc = correct / total
print(f"Block occlusion accuracy (whitened): {acc:.3f}")
print(f"κ(G') = {kappa_after:.1f}  (gate: < {KAPPA_TIGHT} for 'tight')")

if kappa_after < KAPPA_TIGHT and acc >= ACC_PASS:
    print("\nVERDICT: κ IS CAUSAL, THEORY VALIDATED")
elif kappa_after < KAPPA_TIGHT and acc < ACC_PASS:
    print("\nVERDICT: κ IS NOT THE PRIMARY DRIVER")
else:
    print(f"\nVERDICT: SPHERE CONSTRAINT DEFEATS WHITENING (κ'={kappa_after:.1f} > {KAPPA_TIGHT}, inconclusive)")

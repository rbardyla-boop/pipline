"""
STEP 4 (REAL): MNIST with liac-arff parser — no pandas dependency.
Pass/fail thresholds declared BEFORE results:
  Classification: PASS if ≥ 90% under all three corruption types.
  Reconstruction: PASS if faithful (sim ≥ 0.95) ≥ 60% (harder task than clf).
"""

import numpy as np
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tols_v3_phase2 import TangentTOLS

N_UNITS, PATTERN_DIM = 32, 8
FLAT_DIM = N_UNITS * PATTERN_DIM
N_CLASSES = 10
FAITHFUL_THR = 0.95
CLF_PASS = 0.90
FAITHFUL_PASS = 0.60   # per-class sim ≥ 0.95 is harder; 60% is the bar
N_TRIALS = 20
BLOCK_RATE, NOISE_SIGMA, CROSS_RATE = 0.25, 0.3, 0.30

# ---- Declare thresholds BEFORE loading data ----
print("=" * 72)
print("STEP 4 REAL: MNIST")
print("=" * 72)
print(f"\nPRE-DECLARED THRESHOLDS:")
print(f"  Classification pass:   ≥ {CLF_PASS:.0%} per corruption type")
print(f"  Faithful recall pass:  ≥ {FAITHFUL_PASS:.0%} per corruption type (sim ≥ {FAITHFUL_THR})")
print()

t0 = time.time()


def normalize_rows(M):
    norms = np.linalg.norm(M, axis=1, keepdims=True)
    return M / np.maximum(norms, 1e-12)


# ---- Load MNIST ----
try:
    from sklearn.datasets import fetch_openml
    print("  Loading MNIST (parser=liac-arff)...")
    t = time.time()
    mnist = fetch_openml("mnist_784", version=1, as_frame=False,
                         parser="liac-arff", cache=True)
    X = mnist.data.astype(np.float32)
    y = mnist.target.astype(int)
    print(f"  Loaded in {time.time()-t:.1f}s  shape={X.shape}")

    protos = []
    for cls in range(N_CLASSES):
        idx = np.where(y == cls)[0]
        mean_img = X[idx].mean(axis=0)   # (784,)
        # Average-pool 784 → 256
        factor = len(mean_img) // FLAT_DIM
        pooled = mean_img[:FLAT_DIM * factor].reshape(FLAT_DIM, factor).mean(axis=1)
        p = pooled.reshape(N_UNITS, PATTERN_DIM)
        p += np.random.RandomState(cls).randn(*p.shape) * 0.001  # break degeneracy
        protos.append(normalize_rows(p))
    SIMULATED = False
    source = "MNIST"

except Exception as e:
    print(f"  MNIST failed ({type(e).__name__}: {e}). Using structured synthetic.")
    SIMULATED = True
    source = "[SIMULATED]"
    rng = np.random.RandomState(99)
    protos = []
    for cls in range(N_CLASSES):
        v = rng.randn(FLAT_DIM) * 0.2
        b = FLAT_DIM // N_CLASSES
        v[cls*b:(cls+1)*b] += rng.randn(b) * 2.0
        p = v.reshape(N_UNITS, PATTERN_DIM)
        protos.append(normalize_rows(p))

sim_tag = f" {source}" if SIMULATED else ""
print(f"  Source: {source}")

# ---- Build network ----
net = TangentTOLS(n_units=N_UNITS, pattern_dim=PATTERN_DIM, coupling_strength=4.0,
                  dt=0.005, coupling_rule="tensor_pseudo", adaptive_K=True, seed=42)
for p in protos:
    net.store_pattern(p)
proto_flat = np.array([p.flatten() for p in protos])
gram_cond = float(np.linalg.cond(net.G)) if net.G is not None else float("inf")
print(f"  Gram κ(G) = {gram_cond:.3f}")


# ---- Corruption generators ----
def block_cue(target, rng):
    c = target.copy()
    for i in range(max(1, int(N_UNITS * BLOCK_RATE))):
        v = rng.randn(PATTERN_DIM); c[i] = v / np.linalg.norm(v)
    return c

def gauss_cue(target, rng):
    noisy = target + rng.randn(*target.shape) * NOISE_SIGMA
    return normalize_rows(noisy)

def cross_cue(target, distractor):
    blend = (1 - CROSS_RATE) * target + CROSS_RATE * distractor
    return normalize_rows(blend)

def knn(cue_flat):
    return int(np.argmax(proto_flat @ cue_flat))

def softmax_mhn(cue_flat, beta=10.0):
    logits = beta * (proto_flat @ cue_flat)
    logits -= logits.max()
    w = np.exp(logits); w /= w.sum()
    return int(np.argmax(proto_flat @ (w @ proto_flat)))


# ---- Run all three corruption types ----
print(f"\n  N_trials={N_TRIALS} per class per corruption type\n")
print(f"  {'Type':<10} {'Metric':<12}", end="")
for cls in range(N_CLASSES):
    print(f"  cls{cls}", end="")
print("  MEAN")

tols_times, knn_times, smx_times = [], [], []

for corr_type in ["block", "gauss", "cross"]:
    tols_clf_row, tols_faith_row = [], []
    knn_clf_row, smx_clf_row = [], []

    for cls_idx in range(N_CLASSES):
        target = protos[cls_idx]
        # Nearest class by Frobenius overlap (for cross)
        overlaps = [float(np.sum(target * protos[j])) if j != cls_idx else -1e9
                    for j in range(N_CLASSES)]
        distractor = protos[int(np.argmax(overlaps))]

        t_clf, t_faith, k_clf, s_clf = 0, 0, 0, 0
        for trial in range(N_TRIALS):
            rng = np.random.RandomState(42 + cls_idx * 10000 + trial)
            if corr_type == "block":
                cue = block_cue(target, rng)
            elif corr_type == "gauss":
                cue = gauss_cue(target, rng)
            else:
                cue = cross_cue(target, distractor)
            cue_flat = cue.flatten()

            ts = time.perf_counter()
            try:
                recalled, _, _ = net.recall(cue, max_steps=1000, tol=1e-5, log=False)
                sims = [net.pattern_similarity(recalled, p) for p in protos]
                pred = int(np.argmax(sims))
                target_sim = sims[cls_idx]
            except np.linalg.LinAlgError as e:
                print(f"\n  LinAlgError: {e}")
                pred, target_sim = -1, 0.0
            tols_times.append((time.perf_counter() - ts) * 1000)

            ts = time.perf_counter()
            k_pred = knn(cue_flat)
            knn_times.append((time.perf_counter() - ts) * 1000)

            ts = time.perf_counter()
            s_pred = softmax_mhn(cue_flat)
            smx_times.append((time.perf_counter() - ts) * 1000)

            if pred == cls_idx: t_clf += 1
            if target_sim >= FAITHFUL_THR: t_faith += 1
            if k_pred == cls_idx: k_clf += 1
            if s_pred == cls_idx: s_clf += 1

        tols_clf_row.append(t_clf / N_TRIALS)
        tols_faith_row.append(t_faith / N_TRIALS)
        knn_clf_row.append(k_clf / N_TRIALS)
        smx_clf_row.append(s_clf / N_TRIALS)

    def pr(row): return "  ".join(f"{v:.2f}" for v in row)
    mean_tc = np.mean(tols_clf_row)
    mean_tf = np.mean(tols_faith_row)
    mean_kc = np.mean(knn_clf_row)
    mean_sc = np.mean(smx_clf_row)

    flag_tc = " PASS" if mean_tc >= CLF_PASS else " FAIL"
    flag_tf = " PASS" if mean_tf >= FAITHFUL_PASS else " FAIL"

    print(f"  {corr_type:<10} {'TOLS clf':<12}", end="")
    for v in tols_clf_row: print(f"  {v:.2f}", end="")
    print(f"  {mean_tc:.3f}{flag_tc}{sim_tag}")

    print(f"  {corr_type:<10} {'TOLS faith':<12}", end="")
    for v in tols_faith_row: print(f"  {v:.2f}", end="")
    print(f"  {mean_tf:.3f}{flag_tf}{sim_tag}")

    print(f"  {corr_type:<10} {'kNN clf':<12}", end="")
    for v in knn_clf_row: print(f"  {v:.2f}", end="")
    print(f"  {mean_kc:.3f}{sim_tag}")

    print(f"  {corr_type:<10} {'Softmax clf':<12}", end="")
    for v in smx_clf_row: print(f"  {v:.2f}", end="")
    print(f"  {mean_sc:.3f}{sim_tag}")
    print()


# ---- Timing ----
tols_ms = np.mean(tols_times)
knn_ms  = np.mean(knn_times)
smx_ms  = np.mean(smx_times)
print(f"  Timing (mean ms/call): TOLS={tols_ms:.2f}  kNN={knn_ms:.4f}  Softmax={smx_ms:.4f}")
print(f"  TOLS overhead vs kNN: {tols_ms/max(knn_ms,1e-9):.0f}×")

# ---- Save for step5 ----
out = {
    "source": source, "simulated": SIMULATED,
    "timing_ms": {"tols": tols_ms, "knn": knn_ms, "softmax": smx_ms},
}
out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "outputs", "step4_results.json")
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, "w") as f:
    json.dump(out, f, indent=2)

print(f"\n  Elapsed: {time.time()-t0:.1f}s")

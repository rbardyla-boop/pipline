"""
STEP 4: REAL MNIST (or synthetic fallback)
Tests recall under block occlusion, Gaussian noise, and cross-class corruption.
Also benchmarks TOLS vs trivial kNN and one-step softmax retrieval.
"""

import numpy as np
import sys, os, time, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tols_v3_phase2 import TangentTOLS, corrupt

N_UNITS = 32
PATTERN_DIM = 8
FLAT_DIM = N_UNITS * PATTERN_DIM   # 256
N_CLASSES = 10
BASE_K = 4.0
MAX_STEPS = 1000
TOL = 1e-5
FAITHFUL_THR = 0.95
CLF_PASS_THR = 0.90
N_TRIALS = 15
BLOCK_RATE = 0.25
NOISE_SIGMA = 0.3
CROSS_RATE = 0.30

SIMULATED = False


def normalize_rows(M):
    norms = np.linalg.norm(M, axis=1, keepdims=True)
    return M / np.maximum(norms, 1e-12)


# ---- Data loading ----------------------------------------------------

def load_mnist_prototypes():
    global SIMULATED
    # Try sklearn
    try:
        from sklearn.datasets import fetch_openml
        print("  Loading MNIST via sklearn...")
        t = time.time()
        mnist = fetch_openml("mnist_784", version=1, as_frame=False, cache=True)
        X = mnist.data.astype(np.float32)
        y = mnist.target.astype(int)
        print(f"  MNIST loaded in {time.time()-t:.1f}s  shape={X.shape}")
        protos = []
        for cls in range(N_CLASSES):
            idx = np.where(y == cls)[0]
            mean_img = X[idx].mean(axis=0)  # (784,)
            # Average-pool 784 → 256: take every (784//256)=3 pixels, then trim
            factor = len(mean_img) // FLAT_DIM
            trimmed = mean_img[:FLAT_DIM * factor]
            pooled = trimmed.reshape(FLAT_DIM, factor).mean(axis=1)  # (256,)
            p = pooled.reshape(N_UNITS, PATTERN_DIM)
            p += np.random.RandomState(cls).randn(*p.shape) * 0.01
            p = normalize_rows(p)
            protos.append(p)
        return protos, "MNIST"
    except Exception as e:
        print(f"  MNIST failed ({type(e).__name__}: {e}). Using synthetic.")
        SIMULATED = True

    # Synthetic fallback
    rng = np.random.RandomState(99)
    protos = []
    for cls in range(N_CLASSES):
        v = rng.randn(FLAT_DIM) * 0.2
        block = FLAT_DIM // N_CLASSES
        start = cls * block
        v[start:start + block] += rng.randn(block) * 2.0
        p = v.reshape(N_UNITS, PATTERN_DIM)
        p = normalize_rows(p)
        protos.append(p)
    return protos, "[SIMULATED]"


# ---- Corruption types ------------------------------------------------

def block_occlude(pattern, rate, rng):
    c = pattern.copy()
    n = max(1, int(pattern.shape[0] * rate))
    for i in range(n):
        v = rng.randn(pattern.shape[1])
        c[i] = v / np.linalg.norm(v)
    return c


def gaussian_noise(pattern, sigma, rng):
    noisy = pattern + rng.randn(*pattern.shape) * sigma
    return normalize_rows(noisy)


def cross_class_blend(target, distractor, rate):
    blend = (1 - rate) * target + rate * distractor
    return normalize_rows(blend)


# ---- Baselines -------------------------------------------------------

def knn_classify(cue_flat, proto_flat):
    """Argmax cosine similarity — O(n_classes * flat_dim)."""
    sims = proto_flat @ cue_flat / (
        np.linalg.norm(proto_flat, axis=1) * np.linalg.norm(cue_flat) + 1e-12
    )
    return int(np.argmax(sims))


def softmax_retrieve(cue_flat, proto_flat, beta=10.0):
    """One-step modern Hopfield: softmax(β * protos @ cue) @ protos."""
    logits = beta * (proto_flat @ cue_flat)
    logits -= logits.max()
    weights = np.exp(logits)
    weights /= weights.sum()
    retrieved = weights @ proto_flat  # (flat_dim,)
    return int(np.argmax(proto_flat @ retrieved))


# ---- Main test -------------------------------------------------------

print("=" * 72)
print("STEP 4: REAL MNIST / SYNTHETIC FALLBACK")
print("=" * 72)

# Install sklearn if missing
try:
    import sklearn
except ImportError:
    print("  sklearn not found — attempting install...")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "scikit-learn",
         "--break-system-packages", "-q"],
        check=False
    )

t0 = time.time()
protos, source = load_mnist_prototypes()
SIM_TAG = " [SIMULATED]" if SIMULATED else ""
print(f"\n  Source: {source}  N_classes={len(protos)}\n")

# Build TOLS network
net = TangentTOLS(
    n_units=N_UNITS, pattern_dim=PATTERN_DIM, coupling_strength=BASE_K,
    dt=0.005, coupling_rule="tensor_pseudo", adaptive_K=True, seed=42,
)
for p in protos:
    net.store_pattern(p)

proto_flat = np.array([p.flatten() for p in protos])   # (10, 256)

# Corruption configs: label, generator
def make_cues(target_idx, corr_type, trial_rng, distractor):
    target = protos[target_idx]
    if corr_type == "block":
        return block_occlude(target, BLOCK_RATE, trial_rng)
    elif corr_type == "gaussian":
        return gaussian_noise(target, NOISE_SIGMA, trial_rng)
    elif corr_type == "cross":
        return cross_class_blend(target, distractor, CROSS_RATE)

corr_types = ["block", "gaussian", "cross"]

# Per-corruption-type results
type_results = {ct: {"tols_clf": 0, "tols_faithful": 0,
                     "knn_clf": 0, "smx_clf": 0, "total": 0}
                for ct in corr_types}

# Timing accumulators (nanoseconds → ms)
tols_times, knn_times, smx_times = [], [], []

for cls_idx in range(N_CLASSES):
    target = protos[cls_idx]
    # Nearest other class by Gram overlap (for cross-class)
    overlaps = [float(np.sum(target * protos[j])) if j != cls_idx else -1e9
                for j in range(N_CLASSES)]
    distractor = protos[int(np.argmax(overlaps))]

    for ct in corr_types:
        for trial in range(N_TRIALS):
            tr = np.random.RandomState(42 + cls_idx * 10000 + trial + hash(ct) % 1000)

            cue = make_cues(cls_idx, ct, tr, distractor)
            cue_flat = cue.flatten()

            # TOLS recall
            ts = time.perf_counter()
            try:
                recalled, _, _ = net.recall(cue, max_steps=MAX_STEPS, tol=TOL, log=False)
                all_sims = [net.pattern_similarity(recalled, p) for p in protos]
                tols_pred = int(np.argmax(all_sims))
                target_sim = all_sims[cls_idx]
            except np.linalg.LinAlgError as e:
                print(f"  LinAlgError cls={cls_idx} ct={ct} trial={trial}: {e}")
                tols_pred = -1
                target_sim = 0.0
            te = time.perf_counter()
            tols_times.append((te - ts) * 1000)

            # kNN baseline
            ts = time.perf_counter()
            knn_pred = knn_classify(cue_flat, proto_flat)
            te = time.perf_counter()
            knn_times.append((te - ts) * 1000)

            # Softmax baseline
            ts = time.perf_counter()
            smx_pred = softmax_retrieve(cue_flat, proto_flat, beta=10.0)
            te = time.perf_counter()
            smx_times.append((te - ts) * 1000)

            if tols_pred == cls_idx:
                type_results[ct]["tols_clf"] += 1
            if target_sim >= FAITHFUL_THR:
                type_results[ct]["tols_faithful"] += 1
            if knn_pred == cls_idx:
                type_results[ct]["knn_clf"] += 1
            if smx_pred == cls_idx:
                type_results[ct]["smx_clf"] += 1
            type_results[ct]["total"] += 1

# --- Report per-class (block only for brevity) ---
print(f"  Per-class block occlusion (TOLS clf / kNN clf):{SIM_TAG}")
for cls_idx in range(N_CLASSES):
    target = protos[cls_idx]
    distractor = protos[(cls_idx + 1) % N_CLASSES]
    tols_c, knn_c, tot = 0, 0, 0
    for trial in range(N_TRIALS):
        tr = np.random.RandomState(42 + cls_idx * 10000 + trial + hash("block") % 1000)
        cue = block_occlude(target, BLOCK_RATE, tr)
        cue_flat = cue.flatten()
        try:
            recalled, _, _ = net.recall(cue, max_steps=MAX_STEPS, tol=TOL, log=False)
            sims = [net.pattern_similarity(recalled, p) for p in protos]
            if int(np.argmax(sims)) == cls_idx:
                tols_c += 1
        except np.linalg.LinAlgError:
            pass
        if knn_classify(cue_flat, proto_flat) == cls_idx:
            knn_c += 1
        tot += 1
    print(f"    cls={cls_idx}: TOLS={tols_c/tot:.2f}  kNN={knn_c/tot:.2f}{SIM_TAG}")

# --- Summary table ---
print(f"\n  {'Corruption':<14} {'TOLS clf':>10} {'TOLS faith':>12} "
      f"{'kNN clf':>10} {'Softmax clf':>12}{SIM_TAG}")
print("  " + "-" * 62)
all_pass = True
for ct in corr_types:
    r = type_results[ct]
    n = r["total"]
    tc = r["tols_clf"] / n
    tf = r["tols_faithful"] / n
    kc = r["knn_clf"] / n
    sc = r["smx_clf"] / n
    flag = "" if tc >= CLF_PASS_THR else " ← FAIL"
    if tc < CLF_PASS_THR:
        all_pass = False
    print(f"  {ct:<14} {tc:>10.3f} {tf:>12.3f} {kc:>10.3f} {sc:>12.3f}{flag}{SIM_TAG}")

# Timing
tols_ms = np.mean(tols_times)
knn_ms = np.mean(knn_times)
smx_ms = np.mean(smx_times)
print(f"\n  Timing (mean ms/recall):   TOLS={tols_ms:.2f}  kNN={knn_ms:.4f}  Softmax={smx_ms:.4f}")

# Save results for step5
import json
step4_results = {
    "source": source,
    "simulated": SIMULATED,
    "type_results": {
        ct: {
            "tols_clf": type_results[ct]["tols_clf"] / type_results[ct]["total"],
            "tols_faithful": type_results[ct]["tols_faithful"] / type_results[ct]["total"],
            "knn_clf": type_results[ct]["knn_clf"] / type_results[ct]["total"],
            "smx_clf": type_results[ct]["smx_clf"] / type_results[ct]["total"],
        }
        for ct in corr_types
    },
    "timing_ms": {"tols": tols_ms, "knn": knn_ms, "softmax": smx_ms},
}
out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs", "step4_results.json")
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, "w") as f:
    json.dump(step4_results, f, indent=2)
print(f"  Results saved to {out_path}")

sim_note = " [SIMULATED]" if SIMULATED else ""
if all_pass:
    verdict = f"PASS{sim_note}"
    print(f"\n  VERDICT: {verdict} — classification ≥ 90% under all corruption types.")
else:
    verdict = f"FAIL{sim_note}"
    print(f"\n  VERDICT: {verdict} — classification below 90% for at least one corruption type.")

print(f"  Elapsed: {time.time()-t0:.1f}s")

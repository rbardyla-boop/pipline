"""
k_var Calibration Study
=======================
Measures kappa variance for:
  - Synthetic splices of varying strength (high-contrast → feathered → matched)
  - Noisy organic images (real content + σ-noise) through compression
  - Noisy flat images (control group)

Goal: Confirm or refute the SEAM_KAPPA_THRESHOLD = 0.01 separation.
If splice k_var distributions overlap with noisy-organic k_var, the single
threshold is wrong and a joint condition is needed.

Usage:
    python tests/kvar_calibration.py

Output:
    Tabulated k_var by class, min/max/mean for each group,
    and a GO/NO-GO call on the current threshold.
"""
import sys, os
import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from artifact_lens.compression_ladder import CompressionLadder


RNG = np.random.default_rng(42)
LADDER = CompressionLadder()


def kvar_for(path: str) -> float:
    data = LADDER.run(path)["ladder"]
    kappas = np.array([r["kappa"] for r in data])
    return float(np.var(kappas))


def save_tmp(img: np.ndarray, name: str) -> str:
    path = f"/tmp/kvcal_{name}.jpg"
    cv2.imwrite(path, img)
    return path


# ── Load base images ──────────────────────────────────────────────────────────
base_dir = os.path.dirname(os.path.abspath(__file__))
solid     = cv2.imread(os.path.join(base_dir, "dummy_test.png"))        # 256×256 solid red
photo     = cv2.imread(os.path.join(base_dir, "splice_photo_screenshot.png"))  # 512×512 real content
gradient  = cv2.imread(os.path.join(base_dir, "synth_gradient.png"))    # 256×256 gradient

H_s, W_s = solid.shape[:2]
H_p, W_p = photo.shape[:2]

results = {}   # label → k_var


# ══════════════════════════════════════════════════════════════════════════════
# GROUP A — Splices of varying strength
# ══════════════════════════════════════════════════════════════════════════════

def make_splice(base, donor, region_frac=0.4, alpha=1.0, sigma_feather=0):
    """Paste a rectangular crop from donor into base with optional soft mask."""
    out = base.copy().astype(np.float32)
    H, W = base.shape[:2]
    rH, rW = int(H * region_frac), int(W * region_frac)
    y0, x0 = H // 4, W // 4

    donor_r = cv2.resize(donor, (rW, rH)).astype(np.float32)

    if sigma_feather > 0:
        mask = np.ones((rH, rW), dtype=np.float32)
        # Soft edge: fade by sigma_feather pixels on each side
        for i in range(sigma_feather):
            fade = (i + 1) / (sigma_feather + 1)
            mask[:i+1, :] = np.minimum(mask[:i+1, :], fade)
            mask[-(i+1):, :] = np.minimum(mask[-(i+1):, :], fade)
            mask[:, :i+1] = np.minimum(mask[:, :i+1], fade)
            mask[:, -(i+1):] = np.minimum(mask[:, -(i+1):], fade)
        mask = mask[:, :, np.newaxis]
    else:
        mask = alpha

    out[y0:y0+rH, x0:x0+rW] = (
        out[y0:y0+rH, x0:x0+rW] * (1 - mask) + donor_r * mask
    )
    return np.clip(out, 0, 255).astype(np.uint8)


# A1 — Hard splice: solid + gradient (high contrast)
a1 = make_splice(solid, gradient)
results["splice_A1_hard_solid+gradient"] = kvar_for(save_tmp(a1, "a1"))

# A2 — Hard splice: solid + photo crop (high contrast, different texture)
photo_crop = photo[:H_s, :W_s]
a2 = make_splice(solid, photo_crop)
results["splice_A2_hard_solid+photo"] = kvar_for(save_tmp(a2, "a2"))

# A3 — Medium contrast: solid + 50% grey region
grey_patch = np.full_like(solid, 128)
a3 = make_splice(solid, grey_patch)
results["splice_A3_medium_solid+grey"] = kvar_for(save_tmp(a3, "a3"))

# A4 — Low contrast: red solid + slightly different red (±20 levels)
slightly_different = solid.copy()
slightly_different[:, :, 2] = np.clip(int(solid[0, 0, 2]) - 20, 0, 255)
a4 = make_splice(solid, slightly_different)
results["splice_A4_low_contrast"] = kvar_for(save_tmp(a4, "a4"))

# A5 — Very low contrast: ±5 levels
tiny_diff = solid.copy()
tiny_diff[:, :, 2] = np.clip(int(solid[0, 0, 2]) - 5, 0, 255)
a5 = make_splice(solid, tiny_diff)
results["splice_A5_very_low_contrast"] = kvar_for(save_tmp(a5, "a5"))

# A6 — Feathered splice: gradient + photo, 15px soft edge
a6 = make_splice(gradient, cv2.resize(photo_crop, (H_s, W_s)), sigma_feather=15)
results["splice_A6_feathered_15px"] = kvar_for(save_tmp(a6, "a6"))

# A7 — Feathered splice: 30px (heavy blend)
a7 = make_splice(gradient, cv2.resize(photo_crop, (H_s, W_s)), sigma_feather=30)
results["splice_A7_feathered_30px"] = kvar_for(save_tmp(a7, "a7"))

# A8 — Splice on noisy base (photo source + σ=15 noise, then spliced)
noisy_base = solid.copy().astype(np.int16)
noisy_base += RNG.integers(-15, 15, noisy_base.shape, dtype=np.int16)
noisy_base = np.clip(noisy_base, 0, 255).astype(np.uint8)
a8 = make_splice(noisy_base, gradient)
results["splice_A8_noisy_base_σ15"] = kvar_for(save_tmp(a8, "a8"))

# A9 — Matched-lighting splice (histogram equalised donor)
equalized = cv2.equalizeHist(cv2.cvtColor(photo_crop, cv2.COLOR_BGR2GRAY))
eq_bgr = cv2.cvtColor(equalized, cv2.COLOR_GRAY2BGR)
a9 = make_splice(gradient, eq_bgr)
results["splice_A9_eq_matched"] = kvar_for(save_tmp(a9, "a9"))

# A10 — Small region splice (10% of image)
a10 = make_splice(photo_crop, gradient, region_frac=0.1)
results["splice_A10_small_region_10pct"] = kvar_for(save_tmp(a10, "a10"))


# ══════════════════════════════════════════════════════════════════════════════
# GROUP B — Noisy organic (real photo content + noise)
# ══════════════════════════════════════════════════════════════════════════════

def noisy_organic(base, sigma):
    n = RNG.normal(0, sigma, base.shape).astype(np.int16)
    return np.clip(base.astype(np.int16) + n, 0, 255).astype(np.uint8)


for sigma in [5, 10, 15, 20, 30, 50]:
    key = f"noisy_photo_σ{sigma}"
    results[key] = kvar_for(save_tmp(noisy_organic(photo_crop, sigma), key))


# ══════════════════════════════════════════════════════════════════════════════
# GROUP C — Noisy flat (solid red + noise = the P5 failure mode)
# ══════════════════════════════════════════════════════════════════════════════

for sigma in [5, 10, 15, 20, 30, 50]:
    key = f"noisy_solid_σ{sigma}"
    results[key] = kvar_for(save_tmp(noisy_organic(solid, sigma), key))


# ══════════════════════════════════════════════════════════════════════════════
# REPORT
# ══════════════════════════════════════════════════════════════════════════════

THRESHOLD = 0.01

def group_stats(label, keys):
    vals = [results[k] for k in keys if k in results]
    print(f"\n{'─'*64}")
    print(f"  {label}")
    print(f"{'─'*64}")
    for k in keys:
        if k not in results:
            continue
        v = results[k]
        flag = "  ← BELOW THRESHOLD" if v < THRESHOLD else ""
        print(f"  {k:<42s}  k_var={v:.6f}{flag}")
    if vals:
        print(f"  {'min/mean/max':<42s}  {min(vals):.6f} / {np.mean(vals):.6f} / {max(vals):.6f}")
    return vals

splice_keys = [k for k in results if k.startswith("splice_")]
photo_keys  = [k for k in results if k.startswith("noisy_photo")]
solid_keys  = [k for k in results if k.startswith("noisy_solid")]

print("\n" + "═"*64)
print("  k_var CALIBRATION STUDY  (SEAM_KAPPA_THRESHOLD = 0.010)")
print("═"*64)

s_vals = group_stats("GROUP A — Splices", splice_keys)
p_vals = group_stats("GROUP B — Noisy organic (photo + noise)", photo_keys)
f_vals = group_stats("GROUP C — Noisy flat (solid + noise)", solid_keys)

print(f"\n{'═'*64}")
print("  SEPARATION ANALYSIS")
print(f"{'═'*64}")

splice_min  = min(s_vals) if s_vals else 0
noisy_max   = max(p_vals + f_vals) if (p_vals + f_vals) else 0
overlap     = splice_min < noisy_max
below_thresh = [k for k in splice_keys if results[k] < THRESHOLD]

print(f"  Splice    min={splice_min:.6f}  (anything below {THRESHOLD} is a false negative)")
print(f"  Noisy     max={noisy_max:.6f}  (anything above {THRESHOLD} would be a false positive)")

if not below_thresh:
    print(f"\n  ✓ GO  — all splices above threshold, clean separation")
else:
    print(f"\n  ✗ NO-GO  — {len(below_thresh)} splice(s) fall below threshold:")
    for k in below_thresh:
        print(f"     {k}  k_var={results[k]:.6f}")
    if overlap:
        print(f"  Distributions OVERLAP — single threshold is insufficient.")
        print(f"  Need joint condition (k_var + d_mean, or k_range, or noise_floor guard revision).")
    else:
        print(f"  Distributions do not overlap but margin is thin — threshold needs adjustment.")

# Artifact Lens v1.2.5 — Claude Code Build & Test Document

> **Executor:** Claude Code (VSCode Extension)
> **Mode:** Sequential execution — read top to bottom, run every code block, validate every assertion before proceeding.
> **Project Root:** `artifact_lens_project/` — the directory that contains `main.py`.

---

## 0. Pre-Flight Checks

```bash
cd artifact_lens_project    # or wherever main.py lives

python3 --version           # Must be 3.9+
pip show opencv-python numpy matplotlib 2>&1 | grep -E "^(Name|Version)"

# Install missing deps
pip install opencv-python numpy matplotlib --quiet
# Optional: ONNX Runtime (validator falls back to feature-proxy without it)
pip install onnxruntime --quiet
```

**Assert:** `opencv-python`, `numpy`, and `matplotlib` confirmed present.

---

## 1. Package Structure

```
artifact_lens_project/
├── main.py
├── ARTIFACT_LENS_BUILD.md
├── artifact_lens/
│   ├── __init__.py
│   ├── core.py                  # ArtifactLens orchestrator (Conductor)
│   ├── compression_ladder.py    # Target A — Real JPEG physics (19 rungs)
│   ├── reliability.py           # Target B — FRW Active Injection (Δw gate)
│   ├── dynamics.py              # TrajectoryAnalyzer (profile-based classifier)
│   ├── analyzer.py              # Re-export alias → dynamics.TrajectoryAnalyzer
│   ├── segmentation.py          # ManifoldSegmenter (fault-line isolation)
│   ├── segmenter.py             # Re-export alias → segmentation.ManifoldSegmenter
│   ├── validator.py             # Target D — LatentValidator (ONNX-ready)
│   └── dashboard.py             # Target E — ForensicReporter 2×3 grid
├── models/
│   └── (tols_semantic_v1.2.onnx — optional; feature-proxy active without it)
├── tests/
│   ├── dummy_test.png           # Auto-generated on first run
│   └── stress_suite.py          # Target C — Forensic Gauntlet
└── outputs/                     # FORENSIC_*.png reports (auto-created)
```

```bash
mkdir -p artifact_lens models tests outputs
```

---

## 2. File: `artifact_lens/__init__.py`

```bash
cat > artifact_lens/__init__.py << 'EOF'
from .core import ArtifactLens
EOF
```

---

## 3. File: `artifact_lens/compression_ladder.py` (Target A — Real Physics)

19 quality steps (Q=100 → 10 in steps of 5).  Three forensic channels per rung:
ELA (mean abs pixel delta vs. original), FFT (std of log-magnitude spectrum),
Noise (std of Gaussian residual).  Kappa is the spatial coefficient-of-variation
of the per-block inter-rung delta — low for organic images that degrade uniformly,
high for composites where a spliced region reveals its different compression age.
`ela_map` (spatial residual array) is stored in **every** rung dict.

```bash
cat > artifact_lens/compression_ladder.py << 'EOF'
import cv2
import numpy as np
import os
from typing import List, Dict


class CompressionLadder:
    QUALITY_STEPS: List[int] = list(range(100, 9, -5))   # 19 steps: 100…10

    def run(self, image_path: str) -> Dict:
        if not os.path.exists(image_path):
            raise FileNotFoundError(image_path)
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Failed to load: {image_path}")

        original_f = img.astype(np.float32)
        prev_f     = original_f.copy()
        ladder: List[Dict] = []

        for q in self.QUALITY_STEPS:
            compressed = self._jpeg_round_trip(img, q)
            comp_f     = compressed.astype(np.float32)

            ela_diff  = np.abs(original_f - comp_f)
            ela_score = float(np.mean(ela_diff))

            gray      = cv2.cvtColor(compressed, cv2.COLOR_BGR2GRAY).astype(np.float32)
            fft_mag   = np.abs(np.fft.fftshift(np.fft.fft2(gray)))
            fft_score = float(np.std(np.log1p(fft_mag)))

            blurred     = cv2.GaussianBlur(comp_f, (5, 5), 0)
            noise_score = float(np.std(comp_f - blurred))

            kappa        = self._block_kappa(comp_f, prev_f)
            ref_norm     = np.linalg.norm(prev_f) + 1e-8
            disagreement = float(np.var((comp_f - prev_f) / ref_norm))

            ladder.append({
                "quality":      q,
                "ela":          ela_score,
                "fft":          fft_score,
                "noise":        noise_score,
                "kappa":        kappa,
                "disagreement": disagreement,
                "ela_map":      ela_diff,
            })
            prev_f = comp_f

        return {"ladder": ladder}

    def _jpeg_round_trip(self, img: np.ndarray, quality: int) -> np.ndarray:
        _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
        return cv2.imdecode(buf, cv2.IMREAD_COLOR)

    def _block_kappa(self, img_f: np.ndarray, prev_f: np.ndarray,
                     block_size: int = 16) -> float:
        diff = np.mean(np.abs(img_f - prev_f), axis=2)
        h, w = diff.shape
        bm = [
            float(np.mean(diff[y:y + block_size, x:x + block_size]))
            for y in range(0, h - block_size + 1, block_size)
            for x in range(0, w - block_size + 1, block_size)
        ]
        if len(bm) < 2:
            return 1.0
        bm_arr = np.array(bm)
        return float(np.std(bm_arr) / (np.mean(bm_arr) + 1e-8))
EOF
```

---

## 4. File: `artifact_lens/reliability.py` (Target B — FRW Active Injection)

Computes normalised per-feature trust weights (sum to 1.0) from stability and
spike-rate across the 19 rungs.  `compute_weighted_disagreement` produces
Δw = Σ(w_f · σ_f²): the trust-adjusted instability score injected into the
TrajectoryAnalyzer as the Meme Trap gate.

```bash
cat > artifact_lens/reliability.py << 'EOF'
import numpy as np


class FeatureReliabilityWeighter:
    """
    Meme Trap defence:
      Text overlay → ELA spikes, FFT/noise stay calm.
      FRW down-weights ELA → Δw stays low → classifier holds fire.
      Genuine splice → all three features spike together →
      FRW cannot isolate one → Δw rises → COMPOSITE confirmed.
    """

    def __init__(self, spike_threshold_factor: float = 2.0):
        self.spike_factor = spike_threshold_factor

    def compute_weights(self, ladder_results: list) -> dict:
        features = ["ela", "fft", "noise"]
        reliabilities = {}

        for f in features:
            vals = np.array([r[f] for r in ladder_results], dtype=float)

            norm_vals  = (vals - vals.min()) / (vals.max() - vals.min() + 1e-6)
            stability  = 1.0 / (1.0 + np.var(norm_vals))

            diffs       = np.abs(np.diff(vals))
            mean_diff   = np.mean(diffs)
            spike_count = int(np.sum(diffs > mean_diff * self.spike_factor))
            spike_penalty = 1.0 / (1.0 + spike_count)

            reliabilities[f] = stability * spike_penalty

        total = sum(reliabilities.values()) + 1e-12
        return {f: v / total for f, v in reliabilities.items()}

    def compute_weighted_disagreement(self, ladder_results: list,
                                      weights: dict) -> float:
        """Δw = Σ_f ( w_f · σ_f² )"""
        delta_w = 0.0
        for f in ["ela", "fft", "noise"]:
            vals     = np.array([r[f] for r in ladder_results], dtype=float)
            delta_w += weights.get(f, 0.0) * float(np.var(vals))
        return delta_w

    def apply_weighting(self, base_scores: dict, weights: dict) -> float:
        return sum(base_scores[f] * weights[f] for f in base_scores)
EOF
```

---

## 5. File: `artifact_lens/dynamics.py` (TrajectoryAnalyzer)

Profile-based classifier operating on the raw (unscaled) kappa/disagreement
time-series from the ladder.  `delta_w` from FRW modulates the conflict
threshold to prevent the Meme Trap without recalibrating the base thresholds.

```bash
cat > artifact_lens/dynamics.py << 'EOF'
import numpy as np
from typing import Dict, List


class TrajectoryAnalyzer:
    """
    Verdicts:
      ORGANIC                        — real photo, minimal conflict
      SYNTHETIC (OVER-COHERENT)      — AI-generated (too stable across ladder)
      COMPOSITE (MANIFOLD COLLISION) — multiple compression origins detected
      LAUNDERED / COMPRESSED         — real photo with prior compression history
      MALFORMED / ADVERSARIAL        — unstable, high-conflict, non-decodable
      UNKNOWN / INDETERMINATE        — profile combination not in map

    delta_w gate (Meme Trap):
      If FRW-weighted disagreement is low (<= frw_gate), the apparent conflict
      is likely from a single unreliable feature (e.g. ELA on text overlay).
      The "conflict" threshold is raised 2.5×, preventing a false COMPOSITE.
    """

    def __init__(self):
        self.kappa_thresholds    = {"stable": 8.0, "degraded": 20.0}
        self.conflict_thresholds = {"low": 0.02,   "high": 0.08}
        self.frw_gate            = 0.10

    def analyze_trajectory(self, ladder_data: List[Dict],
                            delta_w: float = 0.0) -> Dict:
        kappas       = np.array([r["kappa"]        for r in ladder_data])
        disagreements = np.array([r["disagreement"] for r in ladder_data])

        kappa_slope = float(np.polyfit(range(len(kappas)), kappas, 1)[0])
        kappa_var   = float(np.var(kappas))

        if kappa_var < 2.0 and np.max(kappas) < self.kappa_thresholds["stable"]:
            k_profile = "stable"
        elif kappa_slope > 0.5 and kappa_var > 5.0:
            k_profile = "degrading"
        elif self._is_oscillating(kappas):
            k_profile = "nonlinear"
        else:
            k_profile = "unstable"

        avg_conflict   = float(np.mean(disagreements))
        effective_high = (self.conflict_thresholds["high"]
                          if delta_w >= self.frw_gate
                          else self.conflict_thresholds["high"] * 2.5)

        if avg_conflict < self.conflict_thresholds["low"]:
            d_profile = "coherent"
        elif avg_conflict < effective_high:
            d_profile = "tension"
        else:
            d_profile = "conflict"

        struct_class = self._map_to_structure(k_profile, d_profile)

        return {
            "structural_class":    struct_class,
            "kappa_profile":       k_profile,
            "disagreement_profile": d_profile,
            "metrics": {
                "kappa_slope":      round(kappa_slope, 3),
                "avg_disagreement": round(avg_conflict, 6),
                "delta_w":          round(delta_w, 5),
            },
        }

    def _is_oscillating(self, data: np.ndarray) -> bool:
        diffs = np.diff(data)
        return len(np.where(np.diff(np.sign(diffs)))[0]) > 1

    def _map_to_structure(self, k_p: str, d_p: str) -> str:
        mapping = {
            ("stable",    "coherent"): "ORGANIC",
            ("stable",    "tension"):  "SYNTHETIC (OVER-COHERENT)",
            ("nonlinear", "conflict"): "COMPOSITE (MANIFOLD COLLISION)",
            ("degrading", "coherent"): "LAUNDERED / COMPRESSED",
            ("unstable",  "conflict"): "MALFORMED / ADVERSARIAL",
        }
        return mapping.get((k_p, d_p), "UNKNOWN / INDETERMINATE")
EOF
```

---

## 6. File: `artifact_lens/analyzer.py` (Re-export alias)

```bash
cat > artifact_lens/analyzer.py << 'EOF'
from .dynamics import TrajectoryAnalyzer
__all__ = ["TrajectoryAnalyzer"]
EOF
```

---

## 7. File: `artifact_lens/segmentation.py` (ManifoldSegmenter)

```bash
cat > artifact_lens/segmentation.py << 'EOF'
import cv2
import numpy as np


class ManifoldSegmenter:
    """
    Isolates high-disagreement regions from the ELA heatmap along
    compression fault lines for semantic cross-examination.
    """

    def __init__(self, conflict_threshold: float = 0.65,
                 min_region_area: int = 500):
        self.conflict_thresh = conflict_threshold
        self.min_area        = min_region_area

    def extract_candidates(self, image_path: str,
                           disagreement_heatmap: np.ndarray) -> dict:
        img = cv2.imread(image_path)
        if img is None:
            return {"fault_count": 0, "candidates": []}

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        hm   = cv2.normalize(disagreement_heatmap, None, 0, 255,
                             cv2.NORM_MINMAX).astype(np.uint8)
        _, fault_mask = cv2.threshold(
            hm, int(255 * self.conflict_thresh), 255, cv2.THRESH_BINARY)

        contours, _ = cv2.findContours(
            fault_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        candidates = []
        for i, c in enumerate(contours):
            if cv2.contourArea(c) < self.min_area:
                continue
            x, y, w, h = cv2.boundingRect(c)
            roi            = img[y:y + h, x:x + w]
            local_entropy  = float(
                np.std(cv2.Laplacian(gray[y:y + h, x:x + w], cv2.CV_64F)))
            candidates.append({
                "region_id":     f"manifold_{i}",
                "bbox":          (x, y, w, h),
                "roi_data":      roi,
                "spatial_entropy": local_entropy,
                "role":          "unknown",
            })

        return {"fault_count": len(candidates), "candidates": candidates}
EOF
```

---

## 8. File: `artifact_lens/segmenter.py` (Re-export alias)

```bash
cat > artifact_lens/segmenter.py << 'EOF'
from .segmentation import ManifoldSegmenter
__all__ = ["ManifoldSegmenter"]
EOF
```

---

## 9. File: `artifact_lens/validator.py` (Target D — LatentValidator)

Runs ONNX model when present; falls back to a 50-dim feature proxy that
genuinely discriminates photographic from cartoon/vector regions using
colour histograms, edge density, and luminance variance.

```bash
cat > artifact_lens/validator.py << 'EOF'
import cv2
import numpy as np
from typing import Dict


class LatentValidator:
    """
    Cosine distance >= 0.45  → CONFIRMED_COLLISION
    Cosine distance <  0.45  → ORGANIC / COMPLEX_TEXTURE
    """

    def __init__(self, model_path: str = "models/tols_semantic_v1.2.onnx",
                 threshold: float = 0.45):
        self.threshold = threshold
        self.active    = False
        try:
            import onnxruntime as ort
            self.session = ort.InferenceSession(model_path)
            self.active  = True
            print("ONNX Semantic Model loaded")
        except Exception:
            print("Semantic Model not found — feature-proxy active")

    def get_embedding(self, roi: np.ndarray) -> np.ndarray:
        if self.active:
            blob = cv2.resize(roi, (224, 224)).astype(np.float32) / 255.0
            blob = np.transpose(blob, (2, 0, 1))[np.newaxis, :]
            inputs = {self.session.get_inputs()[0].name: blob}
            return self.session.run(None, inputs)[0].flatten()
        return self._feature_embed(roi)

    def validate_composite(self, segmentation_data: Dict) -> Dict:
        candidates = segmentation_data.get("candidates", [])
        if len(candidates) < 2:
            return {"semantic_conflict": False, "max_latent_distance": 0.0,
                    "status": "INSUFFICIENT_REGIONS",
                    "verdict": "SINGLE_MANIFOLD"}

        embs     = [self.get_embedding(c["roi_data"]) for c in candidates]
        max_dist = 0.0
        for i in range(len(embs)):
            for j in range(i + 1, len(embs)):
                ni, nj = np.linalg.norm(embs[i]), np.linalg.norm(embs[j])
                if ni < 1e-8 or nj < 1e-8:
                    continue
                d = float(1.0 - np.dot(embs[i], embs[j]) / (ni * nj))
                max_dist = max(max_dist, d)

        is_conflict = max_dist >= self.threshold
        return {
            "semantic_conflict":   is_conflict,
            "max_latent_distance": round(max_dist, 4),
            "status":   "VALIDATED" if self.active else "PROXY_ONLY",
            "verdict":  "CONFIRMED_COLLISION" if is_conflict
                        else "ORGANIC / COMPLEX_TEXTURE",
        }

    def _feature_embed(self, roi: np.ndarray) -> np.ndarray:
        if roi is None or roi.size == 0:
            return np.zeros(50)
        r     = cv2.resize(roi, (64, 64))
        hists = []
        for ch in range(3):
            h = cv2.calcHist([r], [ch], None, [16], [0, 256]).flatten()
            hists.extend((h / (h.sum() + 1e-8)).tolist())
        gray         = cv2.cvtColor(r, cv2.COLOR_BGR2GRAY)
        edge_density = float(np.mean(cv2.Canny(gray, 50, 150) > 0))
        lum_var      = float(np.var(gray.astype(np.float32)) / (255.0 ** 2))
        v            = np.array(hists + [edge_density, lum_var], dtype=np.float64)
        return v / (np.linalg.norm(v) + 1e-8)
EOF
```

---

## 10. File: `artifact_lens/dashboard.py` (Target E — ForensicReporter)

2×3 grid: Source | ELA Map | κ Trajectory | FRW Trust Bars | Semantic Status | Verdict.
Saves to `outputs/FORENSIC_<filename>.png` at 150 dpi.  Non-interactive (`Agg` backend).

```bash
cat > artifact_lens/dashboard.py << 'EOF'
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import cv2
import numpy as np
import os


class ForensicReporter:
    PALETTE = {
        "ORGANIC":                         "#27ae60",
        "SYNTHETIC (OVER-COHERENT)":       "#f39c12",
        "COMPOSITE (MANIFOLD COLLISION)":  "#e74c3c",
        "LAUNDERED / COMPRESSED":          "#8e44ad",
        "MALFORMED / ADVERSARIAL":         "#c0392b",
        "ORGANIC / COMPLEX_TEXTURE":       "#2ecc71",
    }

    def generate_report(self, image_path: str, results: dict,
                        output_dir: str = "outputs") -> str:
        os.makedirs(output_dir, exist_ok=True)
        img_name    = os.path.basename(image_path)
        output_path = os.path.join(output_dir, f"FORENSIC_{img_name}.png")

        ladder   = results.get("ladder_data", [])
        ela_map  = results.get("ela_map") or (
            ladder[-1].get("ela_map") if ladder else None)

        return self.render(
            ladder_data    = ladder,
            trajectory     = results.get("trajectory", {}),
            semantic_result= results.get("semantic_validation")
                             if isinstance(results.get("semantic_validation"), dict)
                             else None,
            ela_map        = ela_map,
            feature_trust  = results.get("feature_trust"),
            image_path     = image_path,
            output_path    = output_path,
        )

    def render(self, ladder_data, trajectory, semantic_result=None,
               ela_map=None, feature_trust=None, image_path=None,
               output_path="report.png") -> str:
        fig = plt.figure(figsize=(20, 13), facecolor="#1a1a2e")
        gs  = gridspec.GridSpec(2, 3, figure=fig, hspace=0.45, wspace=0.35)

        self._panel_source(fig.add_subplot(gs[0, 0]), image_path)
        self._panel_ela(fig.add_subplot(gs[0, 1]), ela_map)
        self._panel_kappa(fig.add_subplot(gs[0, 2]), ladder_data, trajectory)
        self._panel_frw(fig.add_subplot(gs[1, 0]), feature_trust)
        self._panel_semantic(fig.add_subplot(gs[1, 1]), semantic_result)
        self._panel_verdict(fig.add_subplot(gs[1, 2]),
                            trajectory.get("structural_class", ""), trajectory)

        fname = os.path.basename(image_path) if image_path else "unknown"
        fig.suptitle(f"Artifact Lens v1.2.5 — Forensic Report\n{fname}",
                     fontsize=15, fontweight="bold", color="white", y=0.98)

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        fig.savefig(output_path, dpi=150, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        plt.close(fig)
        return output_path

    def _panel_source(self, ax, image_path):
        ax.set_facecolor("#0d0d1a")
        if image_path and os.path.exists(image_path):
            img = cv2.cvtColor(cv2.imread(image_path), cv2.COLOR_BGR2RGB)
            ax.imshow(img)
        ax.set_title("SOURCE IMAGE", color="white", fontsize=11, pad=6)
        ax.axis("off")

    def _panel_ela(self, ax, ela_map):
        ax.set_facecolor("#0d0d1a")
        ax.set_title("ELA RESIDUAL (Q=10)", color="white", fontsize=11, pad=6)
        if ela_map is not None:
            g  = np.mean(ela_map, axis=2) if ela_map.ndim == 3 else ela_map
            mn = g.min(); mx = g.max()
            im = ax.imshow((g - mn) / (mx - mn + 1e-8), cmap="inferno")
            plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04).ax.tick_params(colors="white")
        ax.axis("off")

    def _panel_kappa(self, ax, ladder_data, trajectory):
        ax.set_facecolor("#0d0d1a")
        qs = [r["quality"] for r in ladder_data]
        ks = [r["kappa"]   for r in ladder_data]
        ax.plot(qs, ks, "o-", color="#00d2ff", linewidth=2, label="κ")
        ax.axhline(8,  color="#27ae60", linestyle="--", alpha=0.6, label="Stable <8")
        ax.axhline(20, color="#e74c3c", linestyle="--", alpha=0.6, label="Degraded >20")
        ax.set_title(f"κ TRAJECTORY — {trajectory.get('kappa_profile','').upper()}",
                     color="white", fontsize=11, pad=6)
        ax.set_xlabel("JPEG Quality", color="white", fontsize=9)
        ax.invert_xaxis()
        ax.tick_params(colors="white")
        ax.legend(fontsize=8, labelcolor="white", facecolor="#1a1a2e",
                  edgecolor="grey")
        for sp in ax.spines.values():
            sp.set_color("#444466")

    def _panel_frw(self, ax, feature_trust):
        ax.set_facecolor("#0d0d1a")
        ax.set_title("FRW FEATURE TRUST", color="white", fontsize=11, pad=6)
        if feature_trust:
            labels = [k.upper() for k in feature_trust]
            values = list(feature_trust.values())
            bars   = ax.bar(labels, values,
                            color=["#00d2ff","#a29bfe","#fd79a8"], width=0.5)
            for bar, v in zip(bars, values):
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + 0.01,
                        f"{v:.2f}", ha="center", color="white", fontsize=10)
            ax.set_ylim(0, max(values) * 1.25)
        ax.tick_params(colors="white")
        ax.set_ylabel("Trust Weight", color="white", fontsize=9)
        for sp in ax.spines.values():
            sp.set_color("#444466")

    def _panel_semantic(self, ax, semantic_result):
        ax.set_facecolor("#0d0d1a")
        ax.set_title("SEMANTIC GATE", color="white", fontsize=11, pad=6)
        ax.axis("off")
        if isinstance(semantic_result, dict):
            conflict = semantic_result.get("semantic_conflict", False)
            dist     = semantic_result.get("max_latent_distance", 0.0)
            verdict  = semantic_result.get("verdict", "—")
            color    = "#e74c3c" if conflict else "#27ae60"
            ax.text(0.5, 0.75, "CONFLICT" if conflict else "NO CONFLICT",
                    ha="center", va="center", transform=ax.transAxes,
                    fontsize=14, fontweight="bold", color=color)
            ax.text(0.5, 0.50, f"dist = {dist:.4f}",
                    ha="center", va="center", transform=ax.transAxes,
                    fontsize=10, color="white")
            ax.text(0.5, 0.30, verdict, ha="center", va="center",
                    transform=ax.transAxes, fontsize=10, color="#dfe6e9",
                    style="italic")
        else:
            ax.text(0.5, 0.5, "Gate not triggered", ha="center",
                    va="center", transform=ax.transAxes, fontsize=12,
                    color="#636e72")

    def _panel_verdict(self, ax, structural_class, trajectory):
        ax.set_facecolor("#0d0d1a")
        ax.set_title("FINAL VERDICT", color="white", fontsize=11, pad=6)
        ax.axis("off")
        key   = next((k for k in self.PALETTE if structural_class.startswith(k)), None)
        color = self.PALETTE.get(key, "#dfe6e9")
        m     = trajectory.get("metrics", {})
        ax.text(0.5, 0.72, structural_class, ha="center", va="center",
                transform=ax.transAxes, fontsize=12, fontweight="bold",
                color=color,
                bbox=dict(boxstyle="round,pad=0.4", facecolor="#0d0d2e",
                          edgecolor=color, linewidth=2))
        ax.text(0.5, 0.33,
                f"κ profile:    {trajectory.get('kappa_profile','—').upper()}\n"
                f"Disagreement: {trajectory.get('disagreement_profile','—').upper()}\n"
                f"Avg κ slope:  {m.get('kappa_slope','—')}\n"
                f"Avg conflict: {m.get('avg_disagreement','—')}\n"
                f"Δw (FRW):     {m.get('delta_w','—')}",
                ha="center", va="center", transform=ax.transAxes,
                fontsize=9, color="#b2bec3", family="monospace",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="#12122a",
                          edgecolor="#444466"))
EOF
```

---

## 11. File: `artifact_lens/core.py` (Full Orchestrator)

```bash
cat > artifact_lens/core.py << 'EOF'
import os
import numpy as np

from .compression_ladder import CompressionLadder
from .reliability        import FeatureReliabilityWeighter
from .analyzer           import TrajectoryAnalyzer
from .segmenter          import ManifoldSegmenter
from .validator          import LatentValidator
from .dashboard          import ForensicReporter


class ArtifactLens:
    """
    Forensic pipeline orchestrator — Artifact Lens v1.2.5

    process_image() return-dict contract
    -------------------------------------
    structural_class    str
    feature_trust       dict   {ela, fft, noise} normalised weights
    ladder_data         list   19 per-rung dicts (each includes ela_map)
    trajectory          dict   TrajectoryAnalyzer output
    report_path         str    path to saved FORENSIC_*.png
    semantic_validation dict | str
    """

    def __init__(self, output_dir: str = "outputs"):
        self.ladder     = CompressionLadder()
        self.frw        = FeatureReliabilityWeighter()
        self.analyzer   = TrajectoryAnalyzer()
        self.segmenter  = ManifoldSegmenter()
        self.validator  = LatentValidator()
        self.reporter   = ForensicReporter()
        self.output_dir = output_dir

    def process_image(self, image_path: str) -> dict:
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found: {image_path}")

        ladder_results = self.ladder.run(image_path)["ladder"]

        weights = self.frw.compute_weights(ladder_results)
        delta_w = self.frw.compute_weighted_disagreement(ladder_results, weights)

        trajectory = self.analyzer.analyze_trajectory(ladder_results,
                                                       delta_w=delta_w)

        result = {
            "structural_class":   trajectory["structural_class"],
            "feature_trust":      weights,
            "ladder_data":        ladder_results,
            "trajectory":         trajectory,
            "semantic_validation": "Not Required",
        }

        if "COMPOSITE" in trajectory["structural_class"]:
            ela_map = ladder_results[-1].get("ela_map")
            heatmap = self._ela_heatmap(ela_map, ladder_results)
            seg     = self.segmenter.extract_candidates(image_path, heatmap)
            sem     = self.validator.validate_composite(seg)
            result["semantic_validation"] = sem
            if not sem["semantic_conflict"]:
                result["structural_class"] = "ORGANIC / COMPLEX_TEXTURE"

        report_path = self.reporter.generate_report(
            image_path, result, output_dir=self.output_dir)
        result["report_path"] = report_path

        return result

    def _ela_heatmap(self, ela_map, ladder_results) -> np.ndarray:
        if ela_map is not None:
            gray = np.mean(ela_map, axis=2) if ela_map.ndim == 3 else ela_map
            return gray.astype(np.float32)
        avg_d = float(np.mean([r["disagreement"] for r in ladder_results]))
        return np.full((256, 256), avg_d, dtype=np.float32)
EOF
```

---

## 12. File: `main.py` (Entry Point)

```bash
cat > main.py << 'EOF'
import os
import sys
import glob
import cv2
import numpy as np

from artifact_lens.core import ArtifactLens

TESTS_DIR   = "tests"
OUTPUTS_DIR = "outputs"
SUPPORTED   = (".jpg", ".jpeg", ".png", ".webp", ".bmp")


def create_dummy_image() -> str:
    os.makedirs(TESTS_DIR, exist_ok=True)
    path = os.path.join(TESTS_DIR, "dummy_test.png")
    if not os.path.exists(path):
        img = np.zeros((256, 256, 3), dtype=np.uint8)
        img[:, :, 2] = 200
        cv2.imwrite(path, img)
        print(f"  [DUMMY] Created {path}")
    return path


def main():
    print("Artifact Lens v1.2.5 | Forensic Pipeline Active")
    print("-" * 50)

    engine = ArtifactLens(output_dir=OUTPUTS_DIR)
    os.makedirs(TESTS_DIR, exist_ok=True)

    images = sorted(f for f in glob.glob(f"{TESTS_DIR}/*")
                    if f.lower().endswith(SUPPORTED))
    if not images:
        images = [create_dummy_image()]

    summary = []
    for img_path in images:
        print(f"\nAnalyzing: {os.path.basename(img_path)} ...")
        try:
            result = engine.process_image(img_path)
            trust  = result.get("feature_trust", {})
            sem    = result.get("semantic_validation", {})

            print(f"   [VERDICT]  {result['structural_class']}")
            print(f"   [TRUST]    "
                  f"ELA:{trust.get('ela',0):.2f}  "
                  f"FFT:{trust.get('fft',0):.2f}  "
                  f"NOISE:{trust.get('noise',0):.2f}")
            if isinstance(sem, dict):
                print(f"   [SEMANTIC] {sem.get('status')}  "
                      f"dist={sem.get('max_latent_distance',0):.4f}  "
                      f"conflict={sem.get('semantic_conflict', False)}")
            else:
                print(f"   [SEMANTIC] {sem}")
            print(f"   [REPORT]   {result.get('report_path')}")
            summary.append((os.path.basename(img_path), result["structural_class"]))
        except Exception as exc:
            print(f"   [ERROR]    {exc}", file=sys.stderr)
            summary.append((os.path.basename(img_path), "ERROR"))

    print("\n" + "=" * 50)
    print("PIPELINE COMPLETE — VERDICT SUMMARY")
    print("=" * 50)
    for name, verdict in summary:
        print(f"  {name:<45} {verdict}")


if __name__ == "__main__":
    main()
EOF
```

---

## 13. File: `tests/stress_suite.py` (Target C — Forensic Gauntlet)

```bash
mkdir -p tests
cat > tests/stress_suite.py << 'EOF'
"""
Forensic Gauntlet — Target C
Launders organic images through three attack vectors and asserts
structural invariance: organic images must not drift to COMPOSITE or SYNTHETIC.

Usage:
    python tests/stress_suite.py tests/dummy_test.png
    python tests/stress_suite.py test/PXL_20241002_203834091.jpg
Exit code 0 = all pass.  Exit code 1 = structural drift detected.
"""
import sys
import os
import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from artifact_lens.core import ArtifactLens

SAFE_VERDICTS = {
    "ORGANIC", "LAUNDERED / COMPRESSED",
    "ORGANIC / COMPLEX_TEXTURE", "UNKNOWN / INDETERMINATE",
}
FAIL_VERDICTS = {
    "COMPOSITE (MANIFOLD COLLISION)",
    "SYNTHETIC (OVER-COHERENT)",
    "MALFORMED / ADVERSARIAL",
}


class ForensicGauntlet:
    def __init__(self, output_dir: str = "tests/laundered_samples"):
        self.engine     = ArtifactLens(output_dir=output_dir)
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def _launder(self, image_path: str):
        img  = cv2.imread(image_path)
        base = os.path.splitext(os.path.basename(image_path))[0]
        variants = {}

        _, enc = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 30])
        variants["compressed"] = cv2.imdecode(enc, cv2.IMREAD_COLOR)

        gaussian = cv2.GaussianBlur(img, (0, 0), 2.0)
        variants["sharpened"] = cv2.addWeighted(img, 1.5, gaussian, -0.5, 0)

        noise = np.random.default_rng(0).normal(0, 15, img.shape).astype(np.int16)
        variants["noisy"] = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)

        paths = []
        for label, data in variants.items():
            path = os.path.join(self.output_dir, f"{base}_{label}.jpg")
            cv2.imwrite(path, data)
            paths.append((label, path))
        return paths

    def run(self, original_path: str) -> bool:
        print(f"\nStress Testing: {os.path.basename(original_path)}")
        baseline = self.engine.process_image(original_path)["structural_class"]
        print(f"   [BASELINE] {baseline}")
        all_pass = True
        for label, path in self._launder(original_path):
            result    = self.engine.process_image(path)
            new_class = result["structural_class"]
            drifted   = ("ORGANIC" in baseline) and (new_class in FAIL_VERDICTS)
            status    = "FAIL (structural drift)" if drifted else "PASS"
            if drifted:
                all_pass = False
            print(f"   [{label.upper():<12}]  {new_class:<40} {status}")
        return all_pass


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "tests/dummy_test.png"
    if not os.path.exists(target):
        if "dummy_test" in target:
            img = np.zeros((256, 256, 3), dtype=np.uint8)
            img[:, :, 2] = 200
            os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
            cv2.imwrite(target, img)
        else:
            print(f"[ERROR] File not found: {target}")
            sys.exit(1)
    gauntlet = ForensicGauntlet()
    sys.exit(0 if gauntlet.run(target) else 1)
EOF
```

---

## 14. Execution & Validation

### Step 1 — Static syntax check

```bash
python3 -c "
import ast, pathlib, sys
errors = []
for f in sorted(pathlib.Path('artifact_lens').glob('*.py')):
    try:
        ast.parse(f.read_text())
        print(f'  OK  {f}')
    except SyntaxError as e:
        errors.append(str(e))
        print(f'  FAIL {f}: {e}')
sys.exit(len(errors))
"
```

**Assert:** All files print `OK`.

---

### Step 2 — Main pipeline (creates dummy_test.png if tests/ is empty)

```bash
python3 main.py
```

**Expected output:**
```
Artifact Lens v1.2.5 | Forensic Pipeline Active
--------------------------------------------------
Semantic Model not found — feature-proxy active
  [DUMMY] Created tests/dummy_test.png

Analyzing: dummy_test.png ...
   [VERDICT]  ORGANIC
   [TRUST]    ELA:0.xx  FFT:0.xx  NOISE:0.xx
   [SEMANTIC] Not Required
   [REPORT]   outputs/FORENSIC_dummy_test.png.png

==================================================
PIPELINE COMPLETE — VERDICT SUMMARY
==================================================
  dummy_test.png                                ORGANIC
```

**Assert:** No `KeyError`, `ImportError`, or `FileNotFoundError`.  Report path printed.

---

### Step 3 — Return contract verification

```python
# python3 -c "exec(open('tests/contract_check.py').read())"
# — or paste directly into a REPL from the project root —

from artifact_lens.core import ArtifactLens
import os

engine = ArtifactLens()
result = engine.process_image("tests/dummy_test.png")

for key in ("ladder_data","trajectory","feature_trust","structural_class","report_path"):
    assert key in result, f"FAIL: '{key}' missing"
print("PASS: all 5 contract keys present")

n = len(result["ladder_data"])
assert n == 19, f"FAIL: expected 19 ladder steps, got {n}"
print(f"PASS: ladder_data has {n} steps")

for i, step in enumerate(result["ladder_data"]):
    assert "ela_map" in step, f"FAIL: ela_map missing at step {i}"
print("PASS: ela_map present in every rung")

v = result["structural_class"]
assert v == "ORGANIC", f"FAIL: dummy verdict should be ORGANIC, got {v}"
print(f"PASS: dummy_test.png verdict = {v}")

rp = result["report_path"]
assert os.path.exists(rp), f"FAIL: report not found at {rp}"
print(f"PASS: report exists → {rp}")
```

---

### Step 4 — Stress suite

```bash
python3 tests/stress_suite.py tests/dummy_test.png
echo "Exit code: $?"   # Must be 0
```

**Expected:**
```
Stress Testing: dummy_test.png
   [BASELINE] ORGANIC
   [COMPRESSED  ]  ORGANIC                                  PASS
   [SHARPENED   ]  ORGANIC                                  PASS
   [NOISY       ]  ORGANIC                                  PASS
Exit code: 0
```

---

### Step 5 — Real images

```bash
cp /path/to/your/images/* tests/
python3 main.py
```

**Invariant table for real images:**

| Image type | Valid verdicts | Flag immediately if |
|---|---|---|
| Real photo (PXL, DSLR) | `ORGANIC`, `LAUNDERED / COMPRESSED` | `SYNTHETIC`, `COMPOSITE` |
| Meme / text overlay | `LAUNDERED / COMPRESSED`, `ORGANIC / COMPLEX_TEXTURE` | `COMPOSITE` |
| Known AI-generated | `SYNTHETIC (OVER-COHERENT)` | `ORGANIC` |
| Confirmed composite | `COMPOSITE (MANIFOLD COLLISION)` | `ORGANIC` |

---

## 15. Architecture Summary

```
main.py
  └─ ArtifactLens.process_image(path)
       ├─ CompressionLadder.run()              → ladder_data (19 rungs, ela_map per rung)
       ├─ FeatureReliabilityWeighter
       │    ├─ compute_weights()               → normalised trust weights {ela,fft,noise}
       │    └─ compute_weighted_disagreement() → Δw (FRW gate for Meme Trap)
       ├─ TrajectoryAnalyzer.analyze_trajectory(delta_w=Δw)
       │    ├─ kappa profile  (stable / degrading / nonlinear / unstable)
       │    ├─ disagreement profile  (coherent / tension / conflict)
       │    └─ structural_class
       ├─ [if COMPOSITE] ManifoldSegmenter.extract_candidates()  → fault-line ROIs
       ├─ [if COMPOSITE] LatentValidator.validate_composite()    → cosine-dist check
       │    └─ [if no conflict] override → ORGANIC / COMPLEX_TEXTURE
       └─ ForensicReporter.generate_report()   → outputs/FORENSIC_*.png
```

**Key design decision:** `FeatureReliabilityWeighter` produces normalised weights (sum to 1.0).
These are **not** injected as replacement disagreement values (which would break the profile
classifier's calibrated thresholds).  Instead, Δw = Σ(w_f · σ_f²) is passed to
`TrajectoryAnalyzer` as a modulator: when Δw < 0.10, the "conflict" threshold is raised 2.5×,
preventing a single spiking feature (meme text ELA) from triggering a false COMPOSITE.

---

## 16. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: cv2` | Missing dep | `pip install opencv-python` |
| `ModuleNotFoundError: artifact_lens` | Wrong working directory | `cd artifact_lens_project` and verify `__init__.py` exists |
| `KeyError: 'ela_map'` | Old `compression_ladder.py` stub | Rebuild from §3 — current version stores `ela_map` in every rung |
| `Report PNG is black/blank` | `plt.show()` called before `Agg` backend | `matplotlib.use('Agg')` must be the first matplotlib import |
| `dummy_test.png → SYNTHETIC` | FRW-weighted sum used as raw disagreement | Confirm `core.py` passes raw `ladder_results` to `analyze_trajectory`, not a `weighted_ladder` with replaced disagreement values |
| `stress_suite.py exit code 1` | Organic image drifting to COMPOSITE/SYNTHETIC | Check `frw_gate` in `dynamics.py` (default 0.10); consider raising to 0.15 for noisy cameras |
| ONNX session error | Expected; no model file present | `validator.py` falls back to feature-proxy cleanly — no action needed |
| `assert len(ladder_data) == 19` fails | Old 8-step ladder in place | Rebuild `compression_ladder.py` from §3; verify `QUALITY_STEPS = list(range(100, 9, -5))` |

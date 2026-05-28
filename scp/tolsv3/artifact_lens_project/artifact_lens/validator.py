import cv2
import numpy as np
from typing import Dict


class LatentValidator:
    """
    Semantic gate: validates COMPOSITE and GENERATIVE AI hypotheses by
    embedding candidate manifold regions and measuring pairwise cosine distance.

    If regions come from the same latent space (same origin), their feature
    embeddings will be geometrically close.  Cross-manifold inconsistency
    (e.g. photo + vector, real + AI-generated) produces high cosine distance.

    Model path:  models/tols_semantic_v1.2.onnx   (ONNX Runtime, optional)
    Fallback:    50-dim discriminative proxy —
                   color histograms (48-dim, 3ch × 16 bins, L1-normalised)
                 + edge density (1-dim, Canny ratio)
                 + luminance variance (1-dim, normalised)

    Cosine distance ≥ 0.45  → CONFIRMED_COLLISION
    Cosine distance <  0.45 → ORGANIC / COMPLEX_TEXTURE

    Output contract (always):
      regions          int    number of candidate manifold regions evaluated
      max_distance     float  pairwise cosine distance (worst-case pair)
      mean_distance    float  mean pairwise cosine distance across all pairs
      conflict         bool   max_distance ≥ threshold
      status           str    VALIDATED | PROXY_ONLY | INSUFFICIENT_REGIONS
      interpretation   str    human-readable summary
    """

    THRESHOLD = 0.45

    def __init__(self, model_path: str = "models/tols_semantic_v1.2.onnx"):
        self.active = False
        try:
            import onnxruntime as ort
            self.session = ort.InferenceSession(model_path)
            self.active  = True
            print("ONNX Semantic Model loaded")
        except Exception:
            print("Semantic Model not found — feature-proxy active")

    # ------------------------------------------------------------------
    def validate_composite(self, segmentation_data: Dict) -> Dict:
        candidates = segmentation_data.get("candidates", [])

        if len(candidates) < 2:
            return {
                "regions":         len(candidates),
                "max_distance":    0.0,
                "mean_distance":   0.0,
                "conflict":        False,
                "semantic_conflict": False,   # legacy key
                "max_latent_distance": 0.0,   # legacy key
                "status":          "INSUFFICIENT_REGIONS",
                "interpretation":  "Not enough distinct regions to evaluate manifold compatibility.",
            }

        embs = [self._embed(c["roi_data"]) for c in candidates]

        distances = []
        for i in range(len(embs)):
            for j in range(i + 1, len(embs)):
                ni = np.linalg.norm(embs[i])
                nj = np.linalg.norm(embs[j])
                if ni < 1e-8 or nj < 1e-8:
                    continue
                d = float(1.0 - np.dot(embs[i], embs[j]) / (ni * nj))
                distances.append(d)

        if not distances:
            return {
                "regions":         len(candidates),
                "max_distance":    0.0,
                "mean_distance":   0.0,
                "conflict":        False,
                "semantic_conflict": False,
                "max_latent_distance": 0.0,
                "status":          "INSUFFICIENT_REGIONS",
                "interpretation":  "Region embeddings degenerate (near-zero norm).",
            }

        max_dist  = float(max(distances))
        mean_dist = float(np.mean(distances))
        conflict  = max_dist >= self.THRESHOLD
        status    = "VALIDATED" if self.active else "PROXY_ONLY"

        if conflict:
            interpretation = (
                f"Region embeddings not from same latent space "
                f"(max_dist={max_dist:.3f} ≥ {self.THRESHOLD}). "
                "Cross-manifold inconsistency confirmed."
            )
        else:
            interpretation = (
                f"Region embeddings geometrically consistent "
                f"(max_dist={max_dist:.3f} < {self.THRESHOLD}). "
                "Single-origin content likely."
            )

        return {
            "regions":             len(candidates),
            "max_distance":        round(max_dist,  4),
            "mean_distance":       round(mean_dist, 4),
            "conflict":            conflict,
            "semantic_conflict":   conflict,          # legacy key
            "max_latent_distance": round(max_dist, 4),  # legacy key
            "status":              status,
            "interpretation":      interpretation,
        }

    # ------------------------------------------------------------------
    def _embed(self, roi: np.ndarray) -> np.ndarray:
        if self.active:
            return self._onnx_embed(roi)
        return self._proxy_embed(roi)

    def _onnx_embed(self, roi: np.ndarray) -> np.ndarray:
        blob = cv2.resize(roi, (224, 224)).astype(np.float32) / 255.0
        blob = np.transpose(blob, (2, 0, 1))[np.newaxis, :]
        inputs = {self.session.get_inputs()[0].name: blob}
        return self.session.run(None, inputs)[0].flatten()

    def _proxy_embed(self, roi: np.ndarray) -> np.ndarray:
        """50-dim discriminative descriptor (proxy for ONNX embedding)."""
        if roi is None or roi.size == 0:
            return np.zeros(50)

        r = cv2.resize(roi, (64, 64))

        hists = []
        for ch in range(3):
            h = cv2.calcHist([r], [ch], None, [16], [0, 256]).flatten()
            hists.extend((h / (h.sum() + 1e-8)).tolist())

        gray         = cv2.cvtColor(r, cv2.COLOR_BGR2GRAY)
        edge_density = float(np.mean(cv2.Canny(gray, 50, 150) > 0))
        lum_var      = float(np.var(gray.astype(np.float32)) / (255.0 ** 2))

        v = np.array(hists + [edge_density, lum_var], dtype=np.float64)
        n = np.linalg.norm(v)
        return v / (n + 1e-8)

    # ------------------------------------------------------------------
    # Legacy compatibility
    def get_embedding(self, roi: np.ndarray) -> np.ndarray:
        return self._embed(roi)

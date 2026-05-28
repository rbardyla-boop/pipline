import numpy as np
from typing import Dict, List


class TrajectoryAnalyzer:
    """
    Evaluates the physical trajectory of an image across the 19-rung
    compression ladder and maps it to a structural verdict.

    Two independent axes — kappa stability and disagreement level — form a
    state-space whose cells correspond to distinct causal physics:

      (stable,    expected) → ORGANIC                        natural sensor noise
      (stable,    tension)  → COMPOSITE (MANIFOLD COLLISION) seam between regions
      (stable,    conflict) → COMPOSITE (MANIFOLD COLLISION) gross seam / dual origin
      (stable,    coherent) → SYNTHETIC (PURE DIGITAL) / FLAT solid/vector digital
      (nonlinear, coherent) → SYNTHETIC (GENERATIVE AI)      AI manifold drift, low residual
      (nonlinear, expected) → SYNTHETIC (GENERATIVE AI)      AI drift, moderate residual
      (nonlinear, tension)  → SYNTHETIC (SCREENSHOT) / HIGHLY LAUNDERED
      (degrading, coherent) → LAUNDERED / COMPRESSED         re-encoded natural photo
      (unstable,  conflict) → MALFORMED / ADVERSARIAL

    Thresholds calibrated empirically (2026-04-24) against 5-image MN distribution:

      Image type    kappa_var   d_mean
      solid_red     0.000       4.6e-4   → (stable, coherent)
      PXL_photo     0.007       1.3e-3   → (stable, expected)
      Gemini_AI     0.021       5.1e-4   → (nonlinear, coherent)
      splice        0.016       4.8e-3   → (stable, tension)
      screenshot    0.129       1.2e-2   → (nonlinear, tension)

    Surgical upgrades applied:
      - Peak-aware disagreement: d_max surfaces localized seam spikes that
        d_mean would dilute when the explosion is confined to 1-2 rungs.
      - κ-range guard: catches smooth but large κ drift that variance misses.
      - delta_w preserved as a passive FRW diagnostic (not used in routing).
    """

    def __init__(self):
        self.k_var_threshold = 0.02     # above this → structurally non-stable
        self.k_range_limit   = 1.0      # κ swing limit for "stable" guard
        self.d_coherent      = 1.0e-3   # below → coherent (solid color / pure AI)
        # Empirical MN distribution (2026-04-24, n=5):
        #   organic ~1.3e-3, splice ~4.8e-3, screenshot ~1.2e-2
        # Tuned knob — expand calibration set before adjusting.
        self.d_tension       = 3.0e-3   # above → tension (splice / screenshot)

    def analyze_trajectory(self, ladder_data: List[Dict],
                           delta_w: float = 0.0) -> Dict:
        if not ladder_data:
            return {
                "structural_class":     "ERROR: Empty Ladder",
                "kappa_profile":        "unknown",
                "disagreement_profile": "unknown",
                "state":                ("unknown", "unknown"),
                "metrics":              {},
            }

        kappas       = np.array([r.get("kappa",       0.0) for r in ladder_data])
        disagreements = np.array([r.get("disagreement", 0.0) for r in ladder_data])

        k_var   = float(np.var(kappas))
        k_range = float(np.max(kappas) - np.min(kappas))
        k_slope = float(np.polyfit(range(len(kappas)), kappas, 1)[0])
        d_mean  = float(np.mean(disagreements))
        d_max   = float(np.max(disagreements))

        # --- 1. Stability (κ axis) ---
        # "stable"   = uniform compression degradation (no regional hot-spots)
        # "nonlinear" = κ drifts structurally (AI manifold or screenshot vector)
        # "degrading" = monotone κ rise (compressed history baked in)
        if k_var < self.k_var_threshold and k_range < self.k_range_limit:
            stability = "stable"
        elif k_slope > 0.02 and k_var > 0.05:
            stability = "degrading"
        elif self._is_oscillating(kappas):
            stability = "nonlinear"
        else:
            stability = "unstable"

        # --- 2. Agreement (disagreement axis) ---
        # Coherent gate: d_mean alone decides — a d_max spike in a globally-low
        # mean image is single-rung encoding noise (e.g. solid-color JPEG onset).
        # Tension gate: d_max catches localized seam explosions that d_mean
        # dilutes across 19 rungs; d_mean catches sustained high disagreement.
        if d_mean < self.d_coherent:
            agreement = "coherent"
        elif d_max > self.d_tension or d_mean > self.d_tension:
            agreement = "tension"
        else:
            agreement = "expected"

        state        = (stability, agreement)
        struct_class = self._map_to_structure(stability, agreement)

        return {
            "structural_class":     struct_class,
            "kappa_profile":        stability,    # dashboard compatibility
            "disagreement_profile": agreement,
            "state":                state,
            "metrics": {
                "kappa_var":        round(k_var,   5),
                "kappa_range":      round(k_range, 4),
                "kappa_slope":      round(k_slope, 5),
                "d_mean":           round(d_mean,  6),
                "d_max":            round(d_max,   6),
                "delta_w":          round(delta_w, 5),
            },
        }

    # ------------------------------------------------------------------
    def _is_oscillating(self, data: np.ndarray) -> bool:
        diffs = np.diff(data)
        return len(np.where(np.diff(np.sign(diffs)))[0]) > 1

    def _map_to_structure(self, stability: str, agreement: str) -> str:
        mapping = {
            ("stable",    "expected"): "ORGANIC",
            ("stable",    "tension"):  "COMPOSITE (MANIFOLD COLLISION)",
            ("stable",    "conflict"): "COMPOSITE (MANIFOLD COLLISION)",
            ("stable",    "coherent"): "SYNTHETIC (PURE DIGITAL) / FLAT",
            ("nonlinear", "coherent"): "SYNTHETIC (GENERATIVE AI)",
            ("nonlinear", "expected"): "SYNTHETIC (GENERATIVE AI)",
            ("nonlinear", "tension"):  "SYNTHETIC (SCREENSHOT) / HIGHLY LAUNDERED",
            ("degrading", "coherent"): "LAUNDERED / COMPRESSED",
            ("unstable",  "conflict"): "MALFORMED / ADVERSARIAL",
        }
        return mapping.get((stability, agreement), "UNKNOWN / INDETERMINATE")

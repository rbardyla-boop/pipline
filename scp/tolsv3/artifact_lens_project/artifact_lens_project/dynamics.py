import numpy as np
from typing import Dict, List, Tuple

class TrajectoryAnalyzer:
    """
    Classifies image structure based on signal behavior 
    across the compression ladder.
    """
    def __init__(self):
        self.kappa_thresholds = {"stable": 8, "degraded": 20}
        self.conflict_thresholds = {"low": 0.02, "high": 0.08}

    def analyze_trajectory(self, ladder_data: List[Dict]) -> Dict:
        kappas = np.array([r["kappa"] for r in ladder_data])
        disagreements = np.array([r["disagreement"] for r in ladder_data])
        
        # 1. Classify Kappa Profile
        kappa_slope = np.polyfit(range(len(kappas)), kappas, 1)[0]
        kappa_var = np.var(kappas)
        
        if kappa_var < 2.0 and np.max(kappas) < self.kappa_thresholds["stable"]:
            k_profile = "stable"
        elif kappa_slope > 0.5 and kappa_var > 5.0:
            k_profile = "degrading"
        elif self._is_oscillating(kappas):
            k_profile = "nonlinear"
        else:
            k_profile = "unstable"

        # 2. Classify Disagreement Profile
        avg_conflict = np.mean(disagreements)
        if avg_conflict < self.conflict_thresholds["low"]:
            d_profile = "coherent"
        elif avg_conflict < self.conflict_thresholds["high"]:
            d_profile = "tension"
        else:
            d_profile = "conflict"

        # 3. Determine Structural Class
        struct_class = self._map_to_structure(k_profile, d_profile)

        return {
            "kappa_profile": k_profile,
            "disagreement_profile": d_profile,
            "structural_class": struct_class,
            "metrics": {
                "kappa_slope": round(float(kappa_slope), 3),
                "avg_disagreement": round(float(avg_conflict), 4)
            }
        }

    def _is_oscillating(self, data: np.ndarray) -> bool:
        # Check for sign changes in the derivative
        diffs = np.diff(data)
        sign_changes = np.where(np.diff(np.sign(diffs)))[0]
        return len(sign_changes) > 1

    def _map_to_structure(self, k_p: str, d_p: str) -> str:
        mapping = {
            ("stable", "coherent"): "ORGANIC",
            ("stable", "tension"): "SYNTHETIC (OVER-COHERENT)",
            ("nonlinear", "conflict"): "COMPOSITE (MANIFOLD COLLISION)",
            ("degrading", "coherent"): "LAUNDERED / COMPRESSED",
            ("unstable", "conflict"): "MALFORMED / ADVERSARIAL"
        }
        return mapping.get((k_p, d_p), "UNKNOWN / INDETERMINATE")
import numpy as np

class FeatureReliabilityWeighting:
    def __init__(self, spike_threshold_factor=2.0):
        self.spike_factor = spike_threshold_factor

    def compute_weights(self, ladder_results: list) -> dict:
        """
        Analyzes feature series and returns normalized weights.
        """
        features = ["ela", "fft", "noise"]
        raw_series = {f: [r[f] for r in ladder_results] for f in features}
        
        reliabilities = {}
        for f, values in raw_series.items():
            vals = np.array(values)
            
            # 1. Stability (Inverse of Variance)
            # We normalize values to [0,1] first to ensure variance is comparable
            norm_vals = (vals - np.min(vals)) / (np.max(vals) - np.min(vals) + 1e-6)
            stability = 1.0 / (1.0 + np.var(norm_vals))
            
            # 2. Spike Penalty (Robust detection)
            diffs = np.abs(np.diff(vals))
            mean_diff = np.mean(diffs)
            spike_count = np.sum(diffs > (mean_diff * self.spike_factor))
            spike_penalty = 1.0 / (1.0 + spike_count)
            
            reliabilities[f] = stability * spike_penalty

        # Normalize weights so they sum to 1.0
        total = sum(reliabilities.values())
        return {f: r / total for f, r in reliabilities.items()}

    def apply_weighting(self, base_scores: dict, weights: dict) -> float:
        return sum(base_scores[f] * weights[f] for f in base_scores)
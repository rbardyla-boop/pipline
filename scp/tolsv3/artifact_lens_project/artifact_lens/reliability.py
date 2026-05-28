import numpy as np


class FeatureReliabilityWeighter:
    """
    Active FRW: computes per-feature trust weights, then computes a
    FRW-adjusted disagreement score Δw = Σ(w_f · σ_f²).

    Why this matters for the Meme Trap: when an image has a text overlay,
    ELA spikes because text compresses badly, but FFT and noise stay calm.
    FRW detects ELA's high spike-rate, down-weights it, and so Δw stays
    low even though raw disagreement looks alarming.  The TrajectoryAnalyzer
    uses that low Δw to avoid a false COMPOSITE call.

    For a genuine splice, all three features show correlated instability;
    FRW cannot single out one to penalise, so Δw ends up large — confirming
    the physics signal rather than suppressing it.
    """

    def __init__(self, spike_threshold_factor: float = 2.0):
        self.spike_factor = spike_threshold_factor

    def compute_weights(self, ladder_results: list) -> dict:
        features = ["ela", "fft", "noise"]
        reliabilities = {}

        for f in features:
            vals = np.array([r[f] for r in ladder_results], dtype=float)

            # Stability: inverse of normalised variance
            norm_vals = (vals - vals.min()) / (vals.max() - vals.min() + 1e-6)
            stability = 1.0 / (1.0 + np.var(norm_vals))

            # Spike penalty: penalise features that jump erratically
            diffs = np.abs(np.diff(vals))
            mean_diff = np.mean(diffs)
            spike_count = int(np.sum(diffs > mean_diff * self.spike_factor))
            spike_penalty = 1.0 / (1.0 + spike_count)

            reliabilities[f] = stability * spike_penalty

        total = sum(reliabilities.values()) + 1e-12
        return {f: v / total for f, v in reliabilities.items()}

    def compute_weighted_disagreement(self, ladder_results: list,
                                      weights: dict) -> float:
        """
        Δw = Σ_f ( w_f · σ_f² )

        Measures trust-adjusted instability across the compression ladder.
        High Δw → multiple features genuinely disagree → composite likely.
        Low Δw → disagreement is concentrated in a down-weighted feature
                 (e.g., ELA on a text overlay) → meme-trap risk, hold fire.
        """
        delta_w = 0.0
        for f in ["ela", "fft", "noise"]:
            vals = np.array([r[f] for r in ladder_results], dtype=float)
            delta_w += weights.get(f, 0.0) * float(np.var(vals))
        return delta_w

    def apply_weighting(self, base_scores: dict, weights: dict) -> float:
        return sum(base_scores[f] * weights[f] for f in base_scores)

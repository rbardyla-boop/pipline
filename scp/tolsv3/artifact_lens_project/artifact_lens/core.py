import os
import cv2
import numpy as np

from .compression_ladder import CompressionLadder
from .reliability        import FeatureReliabilityWeighter
from .analyzer           import TrajectoryAnalyzer
from .segmenter          import ManifoldSegmenter
from .validator          import LatentValidator
from .dashboard          import ForensicReporter


class ArtifactLens:
    """
    Forensic pipeline orchestrator — Artifact Lens v1.3.0

    process_image() return-dict contract
    -------------------------------------
    structural_class    str     final verdict
    feature_trust       dict    {ela, fft, noise} reliability weights
    ladder_data         list    19 per-rung metric dicts
    trajectory          dict    TrajectoryAnalyzer output
    report_path         str     path to saved FORENSIC_*.png
    semantic_validation dict | str  conflict result or "Not Required"
    noise_floor         float   Laplacian variance (natural-noise diagnostic)
    """

    # Laplacian variance threshold separating flat/vector from natural-noise images.
    # Empirical: solid_red ≈ 0.0, smooth gradient ≈ 0.03, text/UI ≈ 1–20,
    #            noisy solid ≈ 225–900, real photos ≈ 3000–5000.
    NATURAL_NOISE_FLOOR = 15.0

    def __init__(self, output_dir: str = "outputs"):
        self.ladder    = CompressionLadder()
        self.frw       = FeatureReliabilityWeighter()
        self.analyzer  = TrajectoryAnalyzer()
        self.segmenter = ManifoldSegmenter()
        self.validator = LatentValidator()
        self.reporter  = ForensicReporter()
        self.output_dir = output_dir

    def process_image(self, image_path: str) -> dict:
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found: {image_path}")

        # ── Natural noise floor (pre-classification) ─────────────────────
        # Computed first so the verdict refinement step has full context.
        # flat/vector images: lap_var near 0; real content: >> NATURAL_NOISE_FLOOR.
        noise_floor       = self._laplacian_variance(image_path)
        has_natural_noise = noise_floor >= self.NATURAL_NOISE_FLOOR

        # ── Target A: Real JPEG physics ───────────────────────────────────
        ladder_results = self.ladder.run(image_path)["ladder"]

        # ── FRW weight computation ────────────────────────────────────────
        weights = self.frw.compute_weights(ladder_results)

        # ── Target B: Active FRW injection (Δw gate) ─────────────────────
        # Raw disagreement values are NOT replaced; Δw is a passive gate only.
        delta_w = self.frw.compute_weighted_disagreement(ladder_results, weights)

        # ── Trajectory classification ─────────────────────────────────────
        trajectory = self.analyzer.analyze_trajectory(ladder_results,
                                                       delta_w=delta_w)

        # ── Noise-floor verdict refinement (pre-semantic gate) ────────────
        struct  = trajectory["structural_class"]
        m       = trajectory["metrics"]

        if has_natural_noise:
            if struct == "SYNTHETIC (PURE DIGITAL) / FLAT":
                # (stable, coherent) + natural noise → clean DSLR misread as flat/vector.
                struct = "ORGANIC (LOW VARIANCE)"

            elif struct == "SYNTHETIC (GENERATIVE AI)" and trajectory["state"][1] == "coherent":
                # (nonlinear, coherent) + natural noise: an oscillating-κ image with
                # very low d_mean and high Laplacian var. This signal combination is
                # structurally rare (high texture + JPEG-uniform disagreement), but it
                # can occur for real-content images with fine-grained natural texture.
                # Route to ORGANIC (LOW VARIANCE) — the natural-noise flag overrides
                # the synthetic-manifold inference when coherence is the agreement signal.
                struct = "ORGANIC (LOW VARIANCE)"

            elif (struct == "COMPOSITE (MANIFOLD COLLISION)" and
                  m["kappa_var"] < 0.01 and
                  m["d_mean"]    < self.analyzer.d_tension):
                # Joint gate: d_max triggered "tension" but d_mean is in the
                # expected zone — this is a noise-induced d_max spike, not a
                # sustained seam signal.
                #
                # Conditions required to fire (all must hold):
                #   has_natural_noise  — Laplacian var ≥ 15 (real content present)
                #   k_var < 0.01       — no spatially concentrated kappa seam
                #   d_mean < d_tension — sustained disagreement is NOT elevated;
                #                        tension comes from single-rung spike only
                #
                # Safety: real splices with any signal strength have d_mean > d_tension
                # (noisy-splice-σ30: d_mean=5.8e-3 > 3e-3 → gate does NOT fire).
                # Detection floor: splice-on-heavy-noise where d_mean < d_tension
                # is below the physics-based detection floor; no threshold can
                # distinguish it from encoding noise without more signal dimensions.
                struct = "ORGANIC"

        result = {
            "structural_class":  struct,
            "feature_trust":     weights,
            "ladder_data":       ladder_results,
            "trajectory":        trajectory,
            "semantic_validation": "Not Required",
            "noise_floor":       round(noise_floor, 2),
        }

        # ── Target D: Semantic gate (COMPOSITE + GENERATIVE AI) ───────────
        semantic_trigger = "COMPOSITE" in struct or "GENERATIVE AI" in struct
        if semantic_trigger:
            ela_map  = ladder_results[-1].get("ela_map")
            heatmap  = self._ela_heatmap(ela_map, ladder_results)
            seg      = self.segmenter.extract_candidates(image_path, heatmap)
            sem      = self.validator.validate_composite(seg)
            result["semantic_validation"] = sem

            # INSUFFICIENT_REGIONS = uncertain (no evidence), not cleared.
            # Only downgrade when the validator has regions to evaluate and
            # finds no cross-manifold conflict.
            if sem.get("status") != "INSUFFICIENT_REGIONS" and not sem["semantic_conflict"]:
                result["structural_class"] = "ORGANIC / COMPLEX_TEXTURE"

        # ── Target E: Forensic report ─────────────────────────────────────
        report_path = self.reporter.generate_report(
            image_path, result, output_dir=self.output_dir)
        result["report_path"] = report_path

        return result

    # ------------------------------------------------------------------
    def _laplacian_variance(self, image_path: str) -> float:
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return 0.0
        return float(cv2.Laplacian(img.astype(np.float64), cv2.CV_64F).var())

    def _ela_heatmap(self, ela_map, ladder_results) -> np.ndarray:
        if ela_map is not None:
            gray = np.mean(ela_map, axis=2) if ela_map.ndim == 3 else ela_map
            return gray.astype(np.float32)
        avg_d = float(np.mean([r["disagreement"] for r in ladder_results]))
        return np.full((256, 256), avg_d, dtype=np.float32)

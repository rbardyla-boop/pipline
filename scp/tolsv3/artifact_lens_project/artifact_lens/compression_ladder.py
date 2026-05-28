import cv2
import numpy as np
import os
from typing import List, Dict


class CompressionLadder:
    """
    Real JPEG ladder physics: Q=100 → Q=10 in 5-point steps (19 rungs).

    Each rung measures three independent forensic channels:
      ELA   — Mean absolute pixel difference vs. original.
              Organic images degrade smoothly; a spliced region that has a
              prior compression age will show a discontinuous spike.
      FFT   — Std-dev of the log-magnitude spectrum.
              Compression block artefacts create periodic spectral patterns;
              their signature changes non-uniformly for composites.
      Noise — Std-dev of the Gaussian residual (compressed − blurred).
              A reliable proxy for high-frequency artefact energy.

    Kappa uses the spatial coefficient-of-variation of the per-block ELA
    delta between adjacent rungs.  Organic images degrade uniformly (low CoV);
    composites show hot-spots where a region carries a different internal
    compression age (high CoV).
    """

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

            # ELA
            ela_diff  = np.abs(original_f - comp_f)
            ela_score = float(np.mean(ela_diff))

            # FFT
            gray     = cv2.cvtColor(compressed, cv2.COLOR_BGR2GRAY).astype(np.float32)
            fft_mag  = np.abs(np.fft.fftshift(np.fft.fft2(gray)))
            fft_score = float(np.std(np.log1p(fft_mag)))

            # Noise residual
            blurred     = cv2.GaussianBlur(comp_f, (5, 5), 0)
            noise_score = float(np.std(comp_f - blurred))

            # Kappa: spatial CoV of inter-rung delta
            kappa = self._block_kappa(comp_f, prev_f)

            # Normalise by per-pixel mean signal level (resolution-independent).
            # L2-norm grows with sqrt(#pixels), collapsing values to 1e-11 for
            # large images and misaligning the classifier thresholds.
            # Mean-normalised variance stays in [1e-4, 5e-2] across all sizes.
            mean_signal  = float(np.mean(np.abs(prev_f))) + 1e-8
            disagreement = float(np.var((comp_f - prev_f) / mean_signal))

            ladder.append({
                "quality":      q,
                "ela":          ela_score,
                "fft":          fft_score,
                "noise":        noise_score,
                "kappa":        kappa,
                "disagreement": disagreement,
                "ela_map":      ela_diff,   # spatial residual at every rung
            })

            prev_f = comp_f

        return {"ladder": ladder}

    # ------------------------------------------------------------------
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

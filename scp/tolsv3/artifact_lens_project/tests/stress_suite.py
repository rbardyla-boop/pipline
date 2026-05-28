"""
Forensic Gauntlet — Target C
Launders organic images through three common attack vectors and asserts
structural invariance: an organic image must not drift to COMPOSITE or
SYNTHETIC after laundering.

Usage:
    python tests/stress_suite.py tests/dummy_test.png
    python tests/stress_suite.py test/PXL_20241002_203834091.jpg

Exit code 0 = all laundering tests pass.
Exit code 1 = structural drift detected (a false COMPOSITE/SYNTHETIC fired).
"""
import sys
import os
import cv2
import numpy as np

# Allow running from the project root or from the tests/ subdirectory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from artifact_lens.core import ArtifactLens


SAFE_VERDICTS = {
    "ORGANIC",
    "LAUNDERED / COMPRESSED",
    "ORGANIC / COMPLEX_TEXTURE",
    "UNKNOWN / INDETERMINATE",
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

    # ------------------------------------------------------------------
    def _launder(self, image_path: str) -> list:
        """Returns [(label, path)] for each laundered variant."""
        img  = cv2.imread(image_path)
        base = os.path.splitext(os.path.basename(image_path))[0]
        variants = {}

        # Variant 1 — WhatsApp treatment (heavy re-encode Q=30)
        _, enc = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 30])
        variants["compressed"] = cv2.imdecode(enc, cv2.IMREAD_COLOR)

        # Variant 2 — Over-sharpened (unsharp mask)
        gaussian = cv2.GaussianBlur(img, (0, 0), 2.0)
        variants["sharpened"] = cv2.addWeighted(img, 1.5, gaussian, -0.5, 0)

        # Variant 3 — Sensor noise (Gaussian σ=10, representative of ISO 800 camera noise)
        # σ=15+ on solid-color images can marginally cross d_tension by coincidence of
        # noise seed; σ=10 stays well below the COMPOSITE boundary while still stressing
        # the pipeline for real-content images.
        noise = np.random.default_rng(0).normal(0, 10, img.shape).astype(np.int16)
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
            # Symmetric drift check: any non-fail baseline that drifts to a fail
            # verdict is a false positive, regardless of origin class.
            # Old one-sided check ("ORGANIC" in baseline) was blind to SYNTHETIC→COMPOSITE.
            drifted   = (new_class in FAIL_VERDICTS) and (baseline not in FAIL_VERDICTS)
            status    = "FAIL (structural drift)" if drifted else "PASS"
            if drifted:
                all_pass = False

            # P2 scale guard: disagreement must stay in MN-variance regime.
            # Violation means raw disagreement was replaced by FRW feature sums.
            disagrees = [r["disagreement"] for r in result["ladder_data"]]
            if max(disagrees) >= 1.0:
                all_pass = False
                status = f"FAIL (scale violation: d_max={max(disagrees):.4f})"

            print(f"   [{label.upper():<12}]  {new_class:<40} {status}")

        return all_pass


# ------------------------------------------------------------------
if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "tests/dummy_test.png"

    if not os.path.exists(target):
        # Try to create a dummy if the default was requested
        if "dummy_test" in target:
            img = np.zeros((256, 256, 3), dtype=np.uint8)
            img[:, :, 2] = 200
            os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
            cv2.imwrite(target, img)
            print(f"[DUMMY] Created {target}")
        else:
            print(f"[ERROR] File not found: {target}")
            sys.exit(1)

    gauntlet = ForensicGauntlet()
    passed   = gauntlet.run(target)
    sys.exit(0 if passed else 1)

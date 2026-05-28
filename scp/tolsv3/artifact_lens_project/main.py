import os
import sys
import glob
import cv2
import numpy as np

from artifact_lens.core import ArtifactLens

TESTS_DIR = "tests"
OUTPUTS_DIR = "outputs"
SUPPORTED = (".jpg", ".jpeg", ".png", ".webp", ".bmp")


def create_dummy_image() -> str:
    """Creates a solid-red 256×256 test image if tests/ is empty."""
    os.makedirs(TESTS_DIR, exist_ok=True)
    path = os.path.join(TESTS_DIR, "dummy_test.png")
    if not os.path.exists(path):
        img = np.zeros((256, 256, 3), dtype=np.uint8)
        img[:, :, 2] = 200   # red channel
        cv2.imwrite(path, img)
        print(f"  [DUMMY] Created {path}")
    return path


def main():
    print("Artifact Lens v1.2.5 | Forensic Pipeline Active")
    print("-" * 50)

    engine = ArtifactLens(output_dir=OUTPUTS_DIR)
    os.makedirs(TESTS_DIR, exist_ok=True)
    os.makedirs(OUTPUTS_DIR, exist_ok=True)

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
            print(f"   [TRUST]    ELA:{trust.get('ela',0):.2f}  "
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

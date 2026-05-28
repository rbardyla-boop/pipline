import cv2
import numpy as np


class ManifoldSegmenter:
    """
    Slices an image into structurally distinct regions along fault lines
    revealed by the ELA heatmap from the compression ladder.
    """

    def __init__(self, conflict_threshold: float = 0.65,
                 min_region_area: int = 500):
        self.conflict_thresh = conflict_threshold
        self.min_area = min_region_area

    def extract_candidates(self, image_path: str,
                           disagreement_heatmap: np.ndarray) -> dict:
        img = cv2.imread(image_path)
        if img is None:
            return {"fault_count": 0, "candidates": []}

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Normalise heatmap and threshold to find fault lines
        hm = cv2.normalize(disagreement_heatmap, None, 0, 255,
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
            roi = img[y:y + h, x:x + w]
            local_entropy = float(
                np.std(cv2.Laplacian(gray[y:y + h, x:x + w], cv2.CV_64F)))
            candidates.append({
                "region_id": f"manifold_{i}",
                "bbox": (x, y, w, h),
                "roi_data": roi,
                "spatial_entropy": local_entropy,
                "role": "unknown",
            })

        return {"fault_count": len(candidates), "candidates": candidates}

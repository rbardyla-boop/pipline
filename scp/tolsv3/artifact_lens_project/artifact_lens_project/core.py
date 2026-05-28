def process_image(self, image_path: str):
    # 1. Stress Test & Physics (Phase 1 & 2)
    ladder_results = self.ladder.run(image_path)["ladder"]
    weights = self.frw.compute_weights(ladder_results)
    trajectory = self.analyzer.analyze_trajectory(ladder_results)
    
    final_result = {
        "structural_class": trajectory["structural_class"],
        "semantic_validation": "Not Required"
    }

    # 2. Semantic Validation Gate (Phase 3)
    # ONLY trigger semantics if physics suggests a collision or fragile synthetic.
    if "COMPOSITE" in trajectory["structural_class"]:
        # Extract the conflicting regions based on FRW-weighted heatmaps
        seg_data = self.segmenter.extract_candidates(image_path, self._get_heatmap(ladder_results))
        
        # Validate the latent distance
        sem_data = self.validator.validate_composite(seg_data)
        final_result["semantic_validation"] = sem_data
        
        # Override the physics if semantics prove the pieces belong together (e.g., Meme text)
        if not sem_data["semantic_conflict"]:
            final_result["structural_class"] = "LAUNDERED / FALSE_CONFLICT"

    return final_result
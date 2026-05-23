import os
import re
import numpy as np
from itertools import combinations
from typing import Dict, List, Tuple


class V5Simulator:
    """
    Prompt-level approximation of v5 transformer invariants.

    Three simulated invariants injected as mutation context:
    1. Volatile context decay  — session embeddings age per cycle (K_t = K_0 * exp(-λt))
    2. Refractory phrase lockout — high-salience clusters blocked for N cycles
    3. Session trajectory repulsion — session-wide spread check; triggers max divergence if converging

    All state lives in PipelineState (JSON-serializable lists). No instance variables.
    Controlled by V5_SIMULATOR=true env var. Off by default.
    """

    DECAY_RATE = float(os.getenv("V5_DECAY_RATE", "0.05"))
    REFRACTORY_CYCLES = int(os.getenv("V5_REFRACTORY_CYCLES", "2"))
    TRAJECTORY_THRESHOLD = 0.35   # avg pairwise cosine distance; below = session converging

    @staticmethod
    def build_context(
        session_embeddings: List[Dict],
        refractory_clusters: List[Dict],
        current_cycle: int,
    ) -> str:
        """Returns the simulator context block to append to zeitgeist_text before mutation."""
        parts = []

        # 1. Volatile decay — list prior cycle outputs weighted by age
        if len(session_embeddings) > 1:
            aged = []
            for entry in session_embeddings[:-1]:
                age = current_cycle - entry["cycle"]
                weight = max(0.1, 1.0 - age * V5Simulator.DECAY_RATE)
                if weight > 0.2:
                    aged.append(f"  [{weight:.1f}] {entry['preview']}...")
            if aged:
                parts.append(
                    "[V5-DECAY] Prior cycle outputs (weight = constraint strength):\n"
                    + "\n".join(aged)
                    + "\nMove away from all of these proportionally to their listed weight."
                )

        # 2. Refractory lockout — phrases from recent cycles
        active = [
            c for c in refractory_clusters
            if current_cycle - c["cycle_added"] < V5Simulator.REFRACTORY_CYCLES
        ]
        all_phrases = [p for c in active for p in c["phrases"][:3]]
        if all_phrases:
            parts.append(
                "[V5-REFRACTORY] These phrase clusters are locked out this cycle "
                f"(do not use or rephrase): {', '.join(all_phrases[:8])}."
            )

        # 3. Session trajectory repulsion — pairwise spread across all cycles
        if len(session_embeddings) >= 3:
            embs = [np.array(e["emb_list"]) for e in session_embeddings]
            pairs = list(combinations(range(len(embs)), 2))
            if pairs:
                distances = [
                    1.0 - float(np.dot(
                        embs[i] / (np.linalg.norm(embs[i]) + 1e-8),
                        embs[j] / (np.linalg.norm(embs[j]) + 1e-8)
                    ))
                    for i, j in pairs
                ]
                if sum(distances) / len(distances) < V5Simulator.TRAJECTORY_THRESHOLD:
                    parts.append(
                        "[V5-REPULSION] Session trajectory has converged. "
                        "Apply maximum structural divergence. Reject all premise continuations. "
                        "Mutate toward the structural opposite of everything produced so far."
                    )

        return "\n\n".join(parts)

    @staticmethod
    def update_session(
        session_embeddings: List[Dict],
        refractory_clusters: List[Dict],
        trajectory_warnings: int,
        current_cycle: int,
        new_emb: np.ndarray,
        concept: str,
    ) -> Tuple[List[Dict], List[Dict], int]:
        """
        Record this cycle's top candidate embedding and extract refractory phrases.
        Returns (updated_session_embs, updated_refractory, updated_trajectory_warnings).
        """
        new_session = list(session_embeddings) + [{
            "cycle": current_cycle,
            "emb_list": new_emb.tolist(),
            "preview": concept[:60],
        }]

        phrases = V5Simulator.extract_refractory_phrases(concept)
        new_refractory = list(refractory_clusters) + [{"cycle_added": current_cycle, "phrases": phrases}]

        new_warnings = trajectory_warnings
        if len(new_session) >= 3:
            embs = [np.array(e["emb_list"]) for e in new_session]
            pairs = list(combinations(range(len(embs)), 2))
            if pairs:
                distances = [
                    1.0 - float(np.dot(
                        embs[i] / (np.linalg.norm(embs[i]) + 1e-8),
                        embs[j] / (np.linalg.norm(embs[j]) + 1e-8)
                    ))
                    for i, j in pairs
                ]
                if sum(distances) / len(distances) < V5Simulator.TRAJECTORY_THRESHOLD:
                    new_warnings += 1

        return new_session, new_refractory, new_warnings

    @staticmethod
    def extract_refractory_phrases(concept: str) -> List[str]:
        """Extract high-salience phrases using regex (no spacy dependency)."""
        capitalized = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Za-z]+){0,2}\b', concept)
        quoted = re.findall(r'"([^"]{5,40})"', concept)
        all_words = re.findall(r'\b[a-z]{5,}\b', concept.lower())
        freq: Dict[str, int] = {}
        for w in all_words:
            freq[w] = freq.get(w, 0) + 1
        frequent = [w for w, c in freq.items() if c >= 2]
        return list(dict.fromkeys(capitalized[:5] + quoted[:3] + frequent[:3]))

    @staticmethod
    def metrics(
        session_embeddings: List[Dict],
        refractory_clusters: List[Dict],
        trajectory_warnings: int,
        current_cycle: int,
    ) -> Dict:
        active_refractory = sum(
            1 for c in refractory_clusters
            if current_cycle - c["cycle_added"] < V5Simulator.REFRACTORY_CYCLES
        )
        return {
            "simulator_active": True,
            "cycles_tracked": len(session_embeddings),
            "trajectory_warnings": trajectory_warnings,
            "active_refractory_clusters": active_refractory,
        }

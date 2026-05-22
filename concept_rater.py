import sys
import os
import json
import re
import numpy as np
from typing import Dict, Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "clovelearn_phoenix")))
from config import SCORING_RUBRIC, CLAUDE_MODEL
from engine import _call_with_retry

PLATEAU_DELTA = 0.10
MAX_IMPROVEMENT_LOOPS = 4
CONVERGENCE_THRESHOLD = 0.85

FRICTION_PATTERNS = [
    r"physical", r"embodied", r"irreversib", r"cannot be replicated",
    r"in.person", r"in a room", r"gather", r"ritual", r"ceremony",
    r"degrades?", r"wears?", r"burns?", r"buried", r"cannot scale",
    r"local", r"analog", r"handwritten", r"breath", r"touch", r"mortal",
]

ANTI_OPT_PATTERNS = [
    r"no (AI|algorithm|score|dashboard|metric|optimization)",
    r"cannot be optimized", r"refuses? to scale", r"anti.platform",
    r"no telemetry", r"rejects? automation", r"resistance to",
    r"no facilitators?", r"no scores?",
]


class ConceptRater:
    def __init__(self):
        from dotenv import load_dotenv
        from security.firewall import LlamaFirewallClient
        load_dotenv()
        self.client = LlamaFirewallClient()

    def ritual_cost_score(self, text: str) -> float:
        hits = sum(1 for p in FRICTION_PATTERNS if re.search(p, text, re.IGNORECASE))
        return round(min(hits / len(FRICTION_PATTERNS), 1.0), 3)

    def anti_optimization_score(self, text: str) -> float:
        hits = sum(1 for p in ANTI_OPT_PATTERNS if re.search(p, text, re.IGNORECASE))
        return round(min(hits / max(len(ANTI_OPT_PATTERNS), 1), 1.0), 3)

    def detect_convergence(self, emb_a: np.ndarray, emb_b: np.ndarray) -> bool:
        norm_a = emb_a / (np.linalg.norm(emb_a) + 1e-8)
        norm_b = emb_b / (np.linalg.norm(emb_b) + 1e-8)
        return float(np.dot(norm_a, norm_b)) > CONVERGENCE_THRESHOLD

    def rate(self, concept: str, domain: str) -> Dict[str, Any]:
        prompt = f"""Score this {domain} concept on 5 criteria (1-5 each).

CONCEPT:
{concept}

CRITERIA:
1. hook_strength (1-5): Would a one-sentence description stop someone mid-scroll or mid-conversation?
2. specificity (1-5): Is it concrete enough to prototype, greenlight, or pitch to a room?
3. emotional_activation (1-5): Does it hit a real cultural nerve that exists right now in 2026?
4. action_clarity (1-5): Would a founder / director / PM immediately know what to build next?
5. platform_fit (1-5): Does it fill a gap that currently exists in its market?

Return ONLY JSON:
{{"hook_strength": N, "specificity": N, "emotional_activation": N, "action_clarity": N, "platform_fit": N}}"""

        response = _call_with_retry(
            self.client,
            model=CLAUDE_MODEL,
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}]
        )

        raw_text = response.content[0].text
        match = re.search(r"\{[^}]+\}", raw_text)
        if not match:
            raise ValueError(f"No JSON in response: {raw_text}")

        scores = json.loads(match.group())
        composite = round(
            sum(scores[k] * SCORING_RUBRIC[k]["weight"] for k in SCORING_RUBRIC if k in scores),
            3
        )

        sorted_criteria = sorted(scores.items(), key=lambda x: x[1])
        weak_two = sorted_criteria[:2]

        improvement_context = (
            f"\n[CONCEPT IMPROVEMENT DIRECTIVE]\n"
            f"Previous score: {composite}/5.0. Weakest areas: "
            f"{weak_two[0][0]} ({weak_two[0][1]}/5) and {weak_two[1][0]} ({weak_two[1][1]}/5).\n"
            f"In the next mutation, explicitly strengthen {weak_two[0][0].replace('_', ' ')} "
            f"and {weak_two[1][0].replace('_', ' ')}. "
            f"Eliminate abstractions. Ground the concept in a specific mechanism."
        )

        return {
            "scores": scores,
            "composite": composite,
            "improvement_context": improvement_context,
            "weakest": [k for k, _ in weak_two],
            "ritual_cost_score": self.ritual_cost_score(concept),
            "anti_optimization_score": self.anti_optimization_score(concept),
        }

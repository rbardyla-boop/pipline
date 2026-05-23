"""SymbolicGrammarCognition — deterministic CFG mutator, no API calls.

This is Architecture #2, the control arm for A/B comparison against
ClaudeNoveltyCognition. It uses weighted context-free grammar productions
and template substitution to generate candidate mutations.

Design properties:
  - Fully deterministic given a seed (set SYMBOLIC_SEED env var)
  - Zero API calls — no Anthropic, no network
  - No SentenceTransformer by default (uses a cheap hash embedding)
  - Set SYMBOLIC_USE_SENTENCE_TRANSFORMER=true to use the real model
    (required for fair apples-to-apples comparison with Arch #1)

This architecture is ideal for:
  1. CI runs (no credentials needed, < 1ms per cycle)
  2. Isolating loop dynamics from model behaviour
  3. Reproducible baselines with --seed
"""

from __future__ import annotations

import os
import random
import re
from typing import Sequence

from uaf.interfaces.cognition import CognitionEngine


# ------------------------------------------------------------------ #
# Grammar definitions                                                 #
# ------------------------------------------------------------------ #

_SLOTS = {
    "DOMAIN_NOUN": [
        "ritual", "protocol", "engine", "substrate", "lattice",
        "fracture", "threshold", "membrane", "cascade", "artifact",
    ],
    "MODIFIER": [
        "recursive", "entropic", "synthetic", "adversarial", "ephemeral",
        "calibrated", "distributed", "embodied", "asymmetric", "volatile",
    ],
    "ACTION": [
        "decays", "propagates", "crystallizes", "inverts", "fragments",
        "saturates", "escapes", "collapses", "bifurcates", "stabilizes",
    ],
    "CONTEXT_NOUN": [
        "attention", "memory", "governance", "signal", "trajectory",
        "friction", "coherence", "entropy", "resonance", "feedback",
    ],
    "CULTURAL_FRACTURE": [
        "post-optimization anxiety",
        "authenticity scarcity",
        "ritual friction demand",
        "anti-scale impulse",
        "embodied meaning-making",
        "pre-digital nostalgia",
        "sacrifice economy",
        "epistemic drift",
    ],
}

# Production rules: list of (weight, template_string) pairs
# Slots are filled from _SLOTS[KEY] or extracted from context.
_PRODUCTIONS: list[tuple[float, str]] = [
    (0.20, "A {MODIFIER} {DOMAIN_NOUN} that {ACTION} when {CONTEXT_NOUN} exceeds threshold."),
    (0.15, "The {DOMAIN_NOUN} of {CULTURAL_FRACTURE}: a {MODIFIER} system where {CONTEXT_NOUN} {ACTION}."),
    (0.15, "When {CONTEXT_NOUN} {ACTION}, the {MODIFIER} {DOMAIN_NOUN} becomes irreversible."),
    (0.10, "A {MODIFIER} protocol for {CULTURAL_FRACTURE}, built on {DOMAIN_NOUN} that {ACTION}."),
    (0.10, "The intersection of {CULTURAL_FRACTURE} and {MODIFIER} {DOMAIN_NOUN}: {CONTEXT_NOUN} {ACTION}."),
    (0.10, "{CULTURAL_FRACTURE} as a {MODIFIER} {DOMAIN_NOUN}: the {CONTEXT_NOUN} {ACTION}."),
    (0.10, "What if {CONTEXT_NOUN} {ACTION} through a {MODIFIER} {DOMAIN_NOUN}? {CULTURAL_FRACTURE}."),
    (0.10, "A {DOMAIN_NOUN} that transforms {CULTURAL_FRACTURE} into {MODIFIER} {CONTEXT_NOUN}."),
]

# Extract the production weights for random.choices
_PROD_WEIGHTS = [w for w, _ in _PRODUCTIONS]
_PROD_TEMPLATES = [t for _, t in _PRODUCTIONS]

_FRACTURE_RE = re.compile(
    r'\b(?:anxiety|fatigue|sacrifice|nostalgia|crisis|demand|scarcity|'
    r'authentic|embodi|ritual|anti[-\s]|friction|decay|irrevers)\w*\b',
    re.IGNORECASE,
)


class SymbolicGrammarCognition(CognitionEngine):
    """CognitionEngine backed by a weighted CFG + template substitution.

    Args:
        seed: RNG seed for full reproducibility. Defaults to SYMBOLIC_SEED
              env var (int) or 42.
        use_sentence_transformer: Override SYMBOLIC_USE_SENTENCE_TRANSFORMER.
    """

    def __init__(
        self,
        seed: int | None = None,
        use_sentence_transformer: bool | None = None,
    ) -> None:
        effective_seed = seed if seed is not None else int(os.getenv("SYMBOLIC_SEED", "42"))
        self._rng = random.Random(effective_seed)

        use_st_env = os.getenv("SYMBOLIC_USE_SENTENCE_TRANSFORMER", "false").lower() == "true"
        self._use_st = use_sentence_transformer if use_sentence_transformer is not None else use_st_env

        self._st_model = None
        if self._use_st:
            from sentence_transformers import SentenceTransformer
            self._st_model = SentenceTransformer(
                os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
            )

        self._last_trace: list[str] = []

    # ------------------------------------------------------------------ #
    # CognitionEngine                                                     #
    # ------------------------------------------------------------------ #

    def propose(self, parent: str, context: str) -> str:
        """Generate a mutation via CFG template + context-extracted fractures."""
        template = self._rng.choices(_PROD_TEMPLATES, weights=_PROD_WEIGHTS, k=1)[0]
        fractures_from_context = _FRACTURE_RE.findall(context)[:3]

        candidate = self._fill_template(template, fractures_from_context)
        self._last_trace = [
            f"template: {template[:60]}",
            f"parent_preview: {parent[:40]}",
            f"context_fractures: {fractures_from_context}",
        ]
        return candidate

    def embed(self, text: str) -> Sequence[float]:
        """Return embedding vector.

        Default: 384-dim hash-based bag-of-words vector (no model, seeded).
        If SYMBOLIC_USE_SENTENCE_TRANSFORMER=true: use the real SentenceTransformer.
        """
        if self._st_model is not None:
            import numpy as np
            arr = self._st_model.encode(text, normalize_embeddings=True)
            return arr.tolist()
        return self._hash_embed(text, dims=384)

    def coherence(self, candidate: str) -> float:
        """Heuristic coherence: slot-fill ratio + basic grammaticality check."""
        # Count filled slots (words with meaningful length)
        words = re.findall(r'\b[a-zA-Z]{4,}\b', candidate)
        slot_density = min(len(words) / 20.0, 1.0)

        # Bonus for ending with punctuation
        ends_clean = 1.0 if candidate.strip().endswith((".", "?", "!")) else 0.8

        return round(slot_density * ends_clean, 4)

    @property
    def architecture_id(self) -> str:
        return "symbolic_grammar_v1"

    # ------------------------------------------------------------------ #
    # Dynamics hooks                                                      #
    # ------------------------------------------------------------------ #

    def reasoning_trace(self) -> list[str]:
        return list(self._last_trace)

    # ------------------------------------------------------------------ #
    # Internal                                                            #
    # ------------------------------------------------------------------ #

    def _fill_template(self, template: str, context_fractures: list[str]) -> str:
        result = template
        for key, options in _SLOTS.items():
            if f"{{{key}}}" not in result:
                continue
            if key == "CULTURAL_FRACTURE" and context_fractures:
                # Prefer fractures extracted from the live context
                value = self._rng.choice(context_fractures)
            else:
                value = self._rng.choice(options)
            result = result.replace(f"{{{key}}}", value, 1)
        return result

    def _hash_embed(self, text: str, dims: int = 384) -> list[float]:
        """Cheap deterministic embedding: RNG seeded per text hash.

        Each token contributes its hash to a sparse dimension; the result
        is L2-normalised so cosine distance works correctly.
        """
        import hashlib
        import math

        vec = [0.0] * dims
        tokens = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        for token in tokens:
            h = int(hashlib.md5(token.encode()).hexdigest(), 16)
            idx = h % dims
            vec[idx] += 1.0

        norm = math.sqrt(sum(x * x for x in vec))
        if norm < 1e-10:
            # Fallback: hash the whole string
            h = int(hashlib.md5(text.encode()).hexdigest(), 16)
            vec[h % dims] = 1.0
            norm = 1.0
        return [x / norm for x in vec]

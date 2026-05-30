"""ParametricCognition — configurable CognitionEngine for hypothesis testing.

This is the research arm: a single architecture with tunable knobs so that
controlled A/B experiments can isolate the effect of individual parameters.

Parameters exposed for hypothesis testing:
    template_count    (1–8)   — how many production templates are in the pool.
    context_injection (bool)  — whether to extract fractures from zeitgeist context.
    coherence_mode    (str)   — how coherence() scores candidates.
    embed_strategy    (str)   — hash (fast/free) or transformer (semantic).
    seed              (int)   — RNG seed for full reproducibility.

Each instance reports a unique architecture_id derived from its params so that
the ledger can track and compare variants independently.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
import random
from typing import Sequence

from uaf.interfaces.cognition import CognitionEngine


# ------------------------------------------------------------------ #
# Shared grammar (subset of symbolic_grammar for parametric control)  #
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

# Full pool — template_count controls how many are active
_ALL_PRODUCTIONS: list[tuple[float, str]] = [
    (0.20, "A {MODIFIER} {DOMAIN_NOUN} that {ACTION} when {CONTEXT_NOUN} exceeds threshold."),
    (0.15, "The {DOMAIN_NOUN} of {CULTURAL_FRACTURE}: a {MODIFIER} system where {CONTEXT_NOUN} {ACTION}."),
    (0.15, "When {CONTEXT_NOUN} {ACTION}, the {MODIFIER} {DOMAIN_NOUN} becomes irreversible."),
    (0.10, "A {MODIFIER} protocol for {CULTURAL_FRACTURE}, built on {DOMAIN_NOUN} that {ACTION}."),
    (0.10, "The intersection of {CULTURAL_FRACTURE} and {MODIFIER} {DOMAIN_NOUN}: {CONTEXT_NOUN} {ACTION}."),
    (0.10, "{CULTURAL_FRACTURE} as a {MODIFIER} {DOMAIN_NOUN}: the {CONTEXT_NOUN} {ACTION}."),
    (0.10, "What if {CONTEXT_NOUN} {ACTION} through a {MODIFIER} {DOMAIN_NOUN}? {CULTURAL_FRACTURE}."),
    (0.10, "A {DOMAIN_NOUN} that transforms {CULTURAL_FRACTURE} into {MODIFIER} {CONTEXT_NOUN}."),
]

_FRACTURE_RE = re.compile(
    r'\b(?:anxiety|fatigue|sacrifice|nostalgia|crisis|demand|scarcity|'
    r'authentic|embodi|ritual|anti[-\s]|friction|decay|irrevers)\w*\b',
    re.IGNORECASE,
)


class ParametricCognition(CognitionEngine):
    """CognitionEngine with tunable parameters for controlled A/B research.

    Args:
        variant_id:        Explicit ID override; auto-generated from params if omitted.
        template_count:    1–8. Restricts the active production pool.
        context_injection: Inject zeitgeist fractures into templates.
        coherence_mode:    "slot_ratio" | "length" | "entropy"
        embed_strategy:    "hash" | "transformer"
        seed:              RNG seed.
    """

    def __init__(
        self,
        variant_id: str | None = None,
        template_count: int = 8,
        context_injection: bool = True,
        coherence_mode: str = "slot_ratio",
        embed_strategy: str = "hash",
        seed: int = 42,
    ) -> None:
        self._template_count = max(1, min(8, template_count))
        self._context_injection = context_injection
        self._coherence_mode = coherence_mode
        self._embed_strategy = embed_strategy
        self._seed = seed
        self._rng = random.Random(seed)
        self._last_trace: list[str] = []

        # Build active production pool (first N from the full list)
        active = _ALL_PRODUCTIONS[: self._template_count]
        total_w = sum(w for w, _ in active)
        self._prod_weights = [w / total_w for w, _ in active]
        self._prod_templates = [t for _, t in active]

        # Lazy SentenceTransformer
        self._st_model = None

        # Derive a stable architecture_id from the param fingerprint
        if variant_id:
            self._arch_id = variant_id
        else:
            fingerprint = (
                f"tc{self._template_count}"
                f"_ci{int(self._context_injection)}"
                f"_cm{self._coherence_mode[:3]}"
                f"_em{self._embed_strategy[:3]}"
                f"_s{self._seed}"
            )
            self._arch_id = f"parametric_{fingerprint}"

    # ------------------------------------------------------------------ #
    # CognitionEngine                                                     #
    # ------------------------------------------------------------------ #

    def propose(self, parent: str, context: str) -> str:
        template = self._rng.choices(
            self._prod_templates, weights=self._prod_weights, k=1
        )[0]

        fractures: list[str] = []
        if self._context_injection:
            fractures = _FRACTURE_RE.findall(context)[:3]

        candidate = self._fill_template(template, fractures)
        self._last_trace = [
            f"template: {template[:60]}",
            f"parent: {parent[:40]}",
            f"fractures: {fractures}",
            f"context_injection: {self._context_injection}",
            f"template_pool_size: {self._template_count}",
        ]
        return candidate

    def embed(self, text: str) -> Sequence[float]:
        if self._embed_strategy == "transformer":
            return self._transformer_embed(text)
        return self._hash_embed(text, dims=384)

    def coherence(self, candidate: str) -> float:
        if self._coherence_mode == "length":
            return min(len(candidate) / 200.0, 1.0)
        if self._coherence_mode == "entropy":
            return self._entropy_coherence(candidate)
        return self._slot_ratio_coherence(candidate)

    @property
    def architecture_id(self) -> str:
        return self._arch_id

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
                value = self._rng.choice(context_fractures)
            else:
                value = self._rng.choice(options)
            result = result.replace(f"{{{key}}}", value, 1)
        return result

    def _slot_ratio_coherence(self, candidate: str) -> float:
        words = re.findall(r'\b[a-zA-Z]{4,}\b', candidate)
        slot_density = min(len(words) / 20.0, 1.0)
        ends_clean = 1.0 if candidate.strip().endswith((".", "?", "!")) else 0.8
        return round(slot_density * ends_clean, 4)

    def _entropy_coherence(self, candidate: str) -> float:
        words = re.findall(r'\b[a-zA-Z]{3,}\b', candidate.lower())
        if not words:
            return 0.0
        unique = len(set(words))
        diversity = unique / len(words)
        length_bonus = min(len(candidate) / 150.0, 1.0)
        return round(min((diversity * 0.6 + length_bonus * 0.4), 1.0), 4)

    def _hash_embed(self, text: str, dims: int = 384) -> list[float]:
        vec = [0.0] * dims
        tokens = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        for token in tokens:
            h = int(hashlib.md5(token.encode(), usedforsecurity=False).hexdigest(), 16)
            vec[h % dims] += 1.0
        norm = math.sqrt(sum(x * x for x in vec))
        if norm < 1e-10:
            h = int(hashlib.md5(text.encode(), usedforsecurity=False).hexdigest(), 16)
            vec[h % dims] = 1.0
            norm = 1.0
        return [x / norm for x in vec]

    def _transformer_embed(self, text: str) -> list[float]:
        if self._st_model is None:
            from sentence_transformers import SentenceTransformer
            self._st_model = SentenceTransformer(
                os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
            )
        arr = self._st_model.encode(text, normalize_embeddings=True)
        return arr.tolist()

"""EngineerPanel — parallel multi-persona deliberation for variant refinement.

Three engineering personas call Claude concurrently, each applying a different
epistemic lens to the same experiment results. A fourth synthesis call picks
the best 3 proposals from the combined pool.

The panel replaces the single-Claude _refine_variants() call when
hypothesis.panel is set.
"""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from uaf.research.hypothesis import PanelProposal, PersonaSpec, TrialSummary, VariantSpec


# ------------------------------------------------------------------ #
# Default personas                                                    #
# ------------------------------------------------------------------ #

DEFAULT_PERSONAS: list[PersonaSpec] = [
    PersonaSpec(
        name="Research Scientist",
        lens=(
            "Maximize information gain. Every variant must reduce uncertainty "
            "about the research question. Prefer unexplored parameter regions."
        ),
        what_if_bias=(
            "What parameter combination have we NOT tested yet? "
            "What would make the results most surprising or informative?"
        ),
    ),
    PersonaSpec(
        name="Deployed Engineer",
        lens=(
            "Production robustness. A variant that peaks once but is unstable "
            "across seeds is useless in the real world. Consistent mean_score "
            "matters more than best_score."
        ),
        what_if_bias=(
            "What fails at scale or on edge-case seeds? "
            "Which parameter combo collapses when the input distribution shifts?"
        ),
    ),
    PersonaSpec(
        name="Chaos Engineer",
        lens=(
            "Find failure modes and phase boundaries. Push parameters to extremes "
            "and unusual combinations to expose non-linear behaviors, Goodhart "
            "collapse, and concept generation breakdown."
        ),
        what_if_bias=(
            "What breaks the architecture entirely? "
            "Where does score collapse, novelty lock out, or coherence degrade to noise?"
        ),
    ),
]

_PARAM_DOCS = """Available parameters for arch_type="parametric":
  - template_count: int 1-8
  - context_injection: bool
  - coherence_mode: "slot_ratio" | "length" | "entropy"
  - embed_strategy: "hash" | "transformer"
  - seed: int

Also valid: arch_type="symbolic_grammar" with params: seed (int)"""


# ------------------------------------------------------------------ #
# Formatting helpers                                                  #
# ------------------------------------------------------------------ #


def _fmt_summaries(summaries: list[TrialSummary]) -> str:
    lines = []
    for s in summaries:
        lines.append(
            f"  {s.variant_id}: best={s.best_score:.2f} mean={s.mean_score:.2f} "
            f"conv={s.final_convergence:.3f} goodhart={s.goodhart_total}"
        )
        if s.best_candidate:
            lines.append(f"    → {s.best_candidate[:100]}")
    return "\n".join(lines)


def _fmt_proposals(proposals: list[PanelProposal]) -> str:
    lines = []
    for p in proposals:
        lines.append(f"\n[{p.persona}] (confidence={p.confidence:.2f})")
        lines.append(f"  Reasoning: {p.reasoning}")
        lines.append(f"  Proposed variants:")
        for v in p.variants:
            lines.append(f"    - {v.variant_id}: {v.description} | {v.arch_type}: {v.params}")
    return "\n".join(lines)


def _strip_fences(raw: str) -> str:
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip()


# ------------------------------------------------------------------ #
# EngineerPanel                                                       #
# ------------------------------------------------------------------ #


class EngineerPanel:
    """Runs all personas in parallel, then synthesises the best variant set.

    Args:
        personas:   List of PersonaSpec. Defaults to DEFAULT_PERSONAS if None.
        max_workers: Thread pool size for parallel persona calls.
    """

    def __init__(
        self,
        personas: list[PersonaSpec] | None = None,
        max_workers: int = 3,
    ) -> None:
        self._personas = personas if personas is not None else DEFAULT_PERSONAS
        self._max_workers = max_workers

    def deliberate(
        self,
        hypothesis,          # Hypothesis — avoid circular import at module level
        summaries: list[TrialSummary],
        comparison: dict,
        client,
    ) -> tuple[list[VariantSpec], list[PanelProposal]]:
        """Run the full panel deliberation.

        Returns:
            (final_variants, proposals) — final_variants are the 3 selected by
            the synthesis call; proposals are all persona outputs for the journal.
        """
        best_s = max(summaries, key=lambda s: s.best_score)
        findings_block = "\n".join(f"  [{i+1}] {f}" for i, f in enumerate(hypothesis.findings))

        # ── Step 1: parallel persona calls ───────────────────────────
        proposals: list[PanelProposal] = []

        def call_persona(persona: PersonaSpec) -> PanelProposal:
            return self._persona_call(
                persona=persona,
                hypothesis=hypothesis,
                summaries=summaries,
                best_s=best_s,
                findings_block=findings_block,
                client=client,
            )

        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            futures = {pool.submit(call_persona, p): p for p in self._personas}
            for future in as_completed(futures):
                try:
                    proposals.append(future.result())
                except Exception as exc:
                    persona = futures[future]
                    print(f"  [PANEL] {persona.name} call failed: {exc}")

        if not proposals:
            raise RuntimeError("All persona calls failed — no proposals generated")

        # ── Step 2: synthesis ─────────────────────────────────────────
        final_variants = self._synthesis_call(
            hypothesis=hypothesis,
            proposals=proposals,
            client=client,
        )

        return final_variants, proposals

    # ---------------------------------------------------------------- #
    # Persona call                                                      #
    # ---------------------------------------------------------------- #

    def _persona_call(
        self,
        persona: PersonaSpec,
        hypothesis,
        summaries: list[TrialSummary],
        best_s: TrialSummary,
        findings_block: str,
        client,
    ) -> PanelProposal:
        iter_num = hypothesis.iteration
        next_iter = iter_num + 1

        prompt = f"""You are a {persona.name} reviewing AI architecture experiment results.

Your evaluation lens: {persona.lens}
Your "what if" direction: {persona.what_if_bias}

Research question: {hypothesis.question}
Predicted outcome: {hypothesis.predicted_outcome}

Iteration {iter_num} results:
{_fmt_summaries(summaries)}

Best variant so far: {best_s.variant_id} (score={best_s.best_score:.2f})
Best candidate text: {best_s.best_candidate}

Findings so far:
{findings_block}

{_PARAM_DOCS}

From your specific engineering perspective, propose exactly 2 variant specs
that represent your "what if" thinking. Name them "iter{next_iter}_{persona.name[:3].lower()}_v1"
and "iter{next_iter}_{persona.name[:3].lower()}_v2".

Respond ONLY with valid JSON (no markdown, no explanation):
{{
  "persona": "{persona.name}",
  "reasoning": "Your 2-3 sentence what-if thinking from your engineering lens",
  "confidence": 0.0,
  "variants": [
    {{"variant_id": "iter{next_iter}_{persona.name[:3].lower()}_v1", "description": "...", "arch_type": "parametric", "params": {{}}}},
    {{"variant_id": "iter{next_iter}_{persona.name[:3].lower()}_v2", "description": "...", "arch_type": "parametric", "params": {{}}}}
  ]
}}"""

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = _strip_fences(response.content[0].text.strip())
        data = json.loads(raw)

        variants = [VariantSpec.from_dict(v) for v in data.get("variants", [])]
        return PanelProposal(
            persona=data.get("persona", persona.name),
            reasoning=data.get("reasoning", ""),
            variants=variants,
            confidence=float(data.get("confidence", 0.5)),
        )

    # ---------------------------------------------------------------- #
    # Synthesis call                                                    #
    # ---------------------------------------------------------------- #

    def _synthesis_call(
        self,
        hypothesis,
        proposals: list[PanelProposal],
        client,
    ) -> list[VariantSpec]:
        proposals_text = _fmt_proposals(proposals)

        # Build the candidate list explicitly so synthesis only selects, never renames
        all_candidates = []
        for prop in proposals:
            for v in prop.variants:
                all_candidates.append({
                    "variant_id": v.variant_id,
                    "description": v.description,
                    "arch_type": v.arch_type,
                    "params": v.params,
                    "_from_persona": prop.persona,
                })
        candidates_json = json.dumps(all_candidates, indent=2)

        prompt = f"""You are synthesizing variant proposals from {len(proposals)} engineering perspectives.

Research question: {hypothesis.question}

All proposed variants (pick from EXACTLY these, do not rename or create new ones):
{candidates_json}

Select exactly 3 variant_ids from the pool above. Optimise for:
1. Coverage — no two variants should test the same parameter dimension
2. Scientific value — each variant must generate meaningful signal for the research question
3. Balance — include at least one "safe" refinement (near the current best) and one "exploratory" push

Return the 3 selected variants EXACTLY as they appear above (same variant_id, same params).
Do NOT invent new variants or change existing params.

Respond ONLY with a valid JSON array of exactly 3 objects (no markdown):
[
  {{"variant_id": "...", "description": "...", "arch_type": "parametric", "params": {{...}}}},
  {{"variant_id": "...", "description": "...", "arch_type": "parametric", "params": {{...}}}},
  {{"variant_id": "...", "description": "...", "arch_type": "parametric", "params": {{...}}}}
]"""

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = _strip_fences(response.content[0].text.strip())
        specs_data: list[dict] = json.loads(raw)
        return [VariantSpec.from_dict(s) for s in specs_data[:3]]

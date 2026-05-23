"""ExperimentLoop — the discovery meta-loop.

  Define hypothesis → run controlled trials → compare → Claude refines variants
  → repeat until stopping criterion is met.

Claude acts as the scientist: after each iteration it reads the comparison
results and designs the next set of variants to test. The loop terminates when:
  - max_iterations reached (always)
  - any variant hits target_score ("score_threshold" mode)
  - Claude declares the question answered ("hypothesis_confirmed" mode)
"""

from __future__ import annotations

import json
import os
from typing import Any, Callable, TYPE_CHECKING

from uaf.experiments.comparison import best_architecture, compare_traces
from uaf.experiments.runner import ExperimentTrace
from uaf.research.hypothesis import Hypothesis, TrialSummary, VariantSpec
from uaf.research.trial_runner import ControlledTrialRunner


# ------------------------------------------------------------------ #
# Formatting helpers                                                  #
# ------------------------------------------------------------------ #


def _fmt_summaries(summaries: list[TrialSummary]) -> str:
    lines = []
    for s in summaries:
        lines.append(
            f"  {s.variant_id}: best={s.best_score:.2f} mean={s.mean_score:.2f} "
            f"conv={s.final_convergence:.3f} goodhart={s.goodhart_total} "
            f"halt={s.halt_reason}"
        )
        if s.best_candidate:
            lines.append(f"    → {s.best_candidate[:100]}")
    return "\n".join(lines)


def _fmt_comparison(comparison: dict) -> str:
    if not comparison:
        return "  (no comparison data)"
    parts = []
    if "deltas" in comparison:
        for k, v in comparison["deltas"].items():
            parts.append(f"  {k}: {v:+.4f}")
    return "\n".join(parts) if parts else json.dumps(comparison, indent=2)[:400]


# ------------------------------------------------------------------ #
# ExperimentLoop                                                      #
# ------------------------------------------------------------------ #


class ExperimentLoop:
    """Drives the hypothesis → trial → compare → refine → repeat cycle.

    Args:
        max_iterations:    Hard cap on loop iterations regardless of criterion.
        record_to_ledger:  Whether ControlledTrialRunner writes to the ledger.
        client:            anthropic.Anthropic instance; created from env if None.
        verbose:           Print per-iteration summaries.
    """

    def __init__(
        self,
        max_iterations: int = 5,
        record_to_ledger: bool = True,
        client=None,
        verbose: bool = True,
        on_iteration: Callable[[Hypothesis, list[ExperimentTrace], list[TrialSummary], dict], None] | None = None,
    ) -> None:
        self._max_iterations = max_iterations
        self._runner = ControlledTrialRunner(record_to_ledger=record_to_ledger)
        self._client = client
        self._verbose = verbose
        self._on_iteration = on_iteration

    def run(self, hypothesis: Hypothesis) -> Hypothesis:
        """Execute the discovery loop and return the final (possibly resolved) Hypothesis."""
        print(f"\n{'='*64}")
        print(f"  EXPERIMENT LOOP: {hypothesis.hypothesis_id}")
        print(f"  Q: {hypothesis.question}")
        print(f"  Stopping: {hypothesis.stopping_criterion} | max_iter={self._max_iterations}")
        if hypothesis.panel:
            names = [p.name for p in hypothesis.panel]
            print(f"  [PANEL MODE] {len(hypothesis.panel)} personas: {names}")
        else:
            print(f"  [SINGLE-CLAUDE MODE] No panel configured")
        print(f"{'='*64}\n")

        for iteration in range(self._max_iterations):
            hypothesis.iteration = iteration + 1
            print(f"\n[ITER {hypothesis.iteration}] Running {len(hypothesis.variants)} variants...")

            traces = self._runner.run(hypothesis)
            summaries = ControlledTrialRunner.summaries_from_traces(
                hypothesis.variants, traces
            )
            hypothesis.iteration_summaries.append(summaries)

            trace_dicts = [t.to_dict() for t in traces]
            comparison = compare_traces(trace_dicts)
            winner = best_architecture(trace_dicts, metric="best_score")

            finding = self._build_finding(hypothesis, summaries, comparison, winner)
            hypothesis.findings.append(finding)

            if self._on_iteration is not None:
                self._on_iteration(hypothesis, traces, summaries, comparison)

            if self._verbose:
                print(f"\n  Results:")
                print(_fmt_summaries(summaries))
                if "deltas" in comparison:
                    print(f"\n  Deltas:")
                    print(_fmt_comparison(comparison))
                print(f"\n  Best variant: {winner} | Best score so far: {hypothesis.best_score_so_far():.2f}")
                print(f"\n  Finding: {finding}")

            # Check stopping criterion
            resolved, reason = self._should_stop(hypothesis, summaries, comparison)
            if resolved:
                hypothesis.resolved = True
                hypothesis.resolution = reason
                print(f"\n[RESOLVED] {reason}")
                break

            # Not resolved — refine variants for next iteration
            if iteration < self._max_iterations - 1:
                print(f"\n  Refining variants for iteration {hypothesis.iteration + 1}...")
                try:
                    next_variants = self._refine_variants(hypothesis, summaries, comparison)
                    hypothesis.variants = next_variants
                    print(f"  Generated {len(next_variants)} new variants")
                    for v in next_variants:
                        print(f"    {v.variant_id}: {v.description}")
                except Exception as exc:
                    print(f"  [WARN] Variant refinement failed ({exc}), reusing current variants")

        if not hypothesis.resolved:
            hypothesis.resolution = f"max_iterations ({self._max_iterations}) reached"

        print(f"\n[LOOP COMPLETE] {hypothesis.resolution}")
        print(f"  Best score: {hypothesis.best_score_so_far():.2f} | Iterations: {hypothesis.iteration}")
        return hypothesis

    # ------------------------------------------------------------------ #
    # Stopping logic                                                      #
    # ------------------------------------------------------------------ #

    def _should_stop(
        self,
        hypothesis: Hypothesis,
        summaries: list[TrialSummary],
        comparison: dict,
    ) -> tuple[bool, str]:
        if hypothesis.stopping_criterion == "score_threshold":
            best = max(s.best_score for s in summaries)
            if best >= hypothesis.target_score:
                return True, f"Target score {hypothesis.target_score} reached (got {best:.2f})"

        elif hypothesis.stopping_criterion == "hypothesis_confirmed":
            return self._claude_check_resolved(hypothesis, summaries, comparison)

        return False, ""

    def _claude_check_resolved(
        self,
        hypothesis: Hypothesis,
        summaries: list[TrialSummary],
        comparison: dict,
    ) -> tuple[bool, str]:
        """Ask Claude whether the research question has been answered."""
        client = self._get_client()
        prompt = (
            f"Research question: {hypothesis.question}\n"
            f"Predicted outcome: {hypothesis.predicted_outcome}\n\n"
            f"Iteration {hypothesis.iteration} results:\n"
            f"{_fmt_summaries(summaries)}\n\n"
            f"Previous findings:\n" + "\n".join(f"  - {f}" for f in hypothesis.findings[-3:]) + "\n\n"
            "Has this research question been answered with sufficient confidence? "
            "Reply with exactly one of:\n"
            "RESOLVED: <one-sentence explanation>\n"
            "NOT_RESOLVED: <what still needs to be tested>"
        )
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        if text.upper().startswith("RESOLVED"):
            reason = text.split(":", 1)[-1].strip()
            return True, reason
        return False, ""

    # ------------------------------------------------------------------ #
    # Variant refinement                                                  #
    # ------------------------------------------------------------------ #

    def _refine_variants(
        self,
        hypothesis: Hypothesis,
        summaries: list[TrialSummary],
        comparison: dict,
    ) -> list[VariantSpec]:
        """Design the next set of variant specs.

        If hypothesis.panel is set, delegates to EngineerPanel (parallel
        multi-persona deliberation). Otherwise falls back to single-Claude call.
        In both cases applies repetition detection before returning.
        """
        client = self._get_client()

        if hypothesis.panel:
            variants, proposals = self._panel_refine(hypothesis, summaries, comparison, client)
            hypothesis.panel_proposals.append(proposals)
        else:
            variants = self._single_refine(hypothesis, summaries, comparison, client)

        return self._apply_repetition_guard(hypothesis, variants)

    def _panel_refine(
        self,
        hypothesis: Hypothesis,
        summaries: list[TrialSummary],
        comparison: dict,
        client,
    ) -> tuple[list[VariantSpec], list[Any]]:
        from uaf.research.panel import EngineerPanel
        panel = EngineerPanel(personas=hypothesis.panel)
        print(f"  [PANEL] Running {len(hypothesis.panel)} personas in parallel...")
        variants, proposals = panel.deliberate(hypothesis, summaries, comparison, client)
        for p in proposals:
            print(f"    [{p.persona}] confidence={p.confidence:.2f}: {p.reasoning[:80]}")
        return variants, proposals

    def _single_refine(
        self,
        hypothesis: Hypothesis,
        summaries: list[TrialSummary],
        comparison: dict,
        client,
    ) -> list[VariantSpec]:
        """Original single-Claude refinement call."""
        best_so_far = max(s.best_score for s in summaries)
        best_variant = max(summaries, key=lambda s: s.best_score)

        param_docs = """Available parameters for arch_type="parametric":
  - template_count: int 1-8 (production pool size; more = more diverse)
  - context_injection: bool (extract zeitgeist fractures from context)
  - coherence_mode: "slot_ratio" | "length" | "entropy"
  - embed_strategy: "hash" | "transformer"
  - seed: int (for reproducibility)

Also valid: arch_type="symbolic_grammar" with params: seed (int), use_sentence_transformer (bool)"""

        findings_block = "\n".join(f"  [{i+1}] {f}" for i, f in enumerate(hypothesis.findings))

        prompt = f"""You are an AI architecture researcher running controlled experiments.

Research question: {hypothesis.question}
Predicted outcome: {hypothesis.predicted_outcome}

Iteration {hypothesis.iteration} results (best_score / mean_score / convergence):
{_fmt_summaries(summaries)}

Deltas vs first variant:
{_fmt_comparison(comparison)}

Findings so far:
{findings_block}

Best variant so far: {best_variant.variant_id} (score={best_so_far:.2f})
Best candidate text: {best_variant.best_candidate}

{param_docs}

Design exactly 3 new variant specs that will most efficiently advance the research question.
Vary ONE parameter at a time. Use the best-performing variant as the baseline to build from.
Name variants using the pattern "iter{hypothesis.iteration + 1}_v1", "iter{hypothesis.iteration + 1}_v2", etc.

IMPORTANT: Do NOT propose parameter combinations identical to variants already tested.

Respond ONLY with a valid JSON array, no markdown, no explanation:
[
  {{
    "variant_id": "iter{hypothesis.iteration + 1}_v1",
    "description": "specific one-line description of what this tests",
    "arch_type": "parametric",
    "params": {{...}}
  }}
]"""

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()
        specs_data: list[dict] = json.loads(raw)
        return [VariantSpec.from_dict(s) for s in specs_data]

    def _apply_repetition_guard(
        self,
        hypothesis: Hypothesis,
        variants: list[VariantSpec],
    ) -> list[VariantSpec]:
        """Detect repeated param combos and force at least one novel variant.

        A variant is considered a repeat if ≥2 of its params exactly match
        a variant that was already run in any previous iteration.
        """
        seen_params: list[dict] = []
        for iteration in hypothesis.iteration_summaries:
            for s in iteration:
                # Reconstruct params from architecture_id is not reliable;
                # instead pull from the hypothesis.variants list at time of run.
                pass
        # Collect all previously proposed variant params from hypothesis spec history
        # We track via a frozen-key approach on the current variants list
        # (the best we can do without a full param ledger)
        repeat_count = 0
        for v in variants:
            # Check against iter1 variants stored on the hypothesis
            for prev_iter_summaries in hypothesis.iteration_summaries:
                for s in prev_iter_summaries:
                    if s.variant_id == v.variant_id:
                        repeat_count += 1

        if repeat_count > len(variants) // 2:
            print(f"  [GUARD] {repeat_count}/{len(variants)} repeated variant IDs detected — forcing seed diversity")
            for i, v in enumerate(variants):
                v.params = {**v.params, "seed": (v.params.get("seed", 42) + 100 * (hypothesis.iteration + 1) + i)}
                v.variant_id = f"{v.variant_id}_g{hypothesis.iteration}"
                v.description = f"{v.description} [guard-diversified]"

        return variants

    # ------------------------------------------------------------------ #
    # Finding summariser                                                  #
    # ------------------------------------------------------------------ #

    def _build_finding(
        self,
        hypothesis: Hypothesis,
        summaries: list[TrialSummary],
        comparison: dict,
        winner: str | None,
    ) -> str:
        scores = {s.variant_id: s.best_score for s in summaries}
        sorted_variants = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        ranking = ", ".join(f"{v}={s:.2f}" for v, s in sorted_variants)
        return (
            f"Iter {hypothesis.iteration}: {ranking}. "
            f"Winner: {winner or 'tie'}. "
            f"Best score this iteration: {max(scores.values()):.2f}."
        )

    # ------------------------------------------------------------------ #
    # Client helper                                                       #
    # ------------------------------------------------------------------ #

    def _get_client(self):
        if self._client is not None:
            return self._client
        import anthropic
        from dotenv import load_dotenv
        load_dotenv()
        return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

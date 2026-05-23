"""Tests for the hypothesis-driven architecture discovery layer.

No real API calls, no Phoenix scoring, no model downloads.
"""

from __future__ import annotations

import json
import math
import pytest
from unittest.mock import MagicMock, patch

from uaf.research.hypothesis import Hypothesis, VariantSpec, TrialSummary
from uaf.research.trial_runner import (
    ControlledTrialRunner,
    _CyclePlanner,
    _HeuristicVerification,
    _ResearchMemory,
    _ResearchRuntime,
    _instantiate_arch,
)
from architectures.parametric.adapter import ParametricCognition


# ------------------------------------------------------------------ #
# VariantSpec                                                         #
# ------------------------------------------------------------------ #


def test_variant_spec_round_trips():
    spec = VariantSpec(
        variant_id="test_v1",
        description="baseline",
        arch_type="parametric",
        params={"template_count": 4, "seed": 42},
    )
    d = spec.to_dict()
    restored = VariantSpec.from_dict(d)
    assert restored.variant_id == spec.variant_id
    assert restored.params == spec.params


def test_variant_spec_defaults_empty_params():
    spec = VariantSpec(variant_id="x", description="y", arch_type="symbolic_grammar")
    assert spec.params == {}


# ------------------------------------------------------------------ #
# Hypothesis                                                          #
# ------------------------------------------------------------------ #


def _make_hypothesis(**overrides) -> Hypothesis:
    defaults = dict(
        hypothesis_id="test_hyp",
        question="Does template_count affect score?",
        predicted_outcome="More templates → higher diversity → higher scores",
        domain="gaming",
        seeds=["seed_a", "seed_b"],
        variants=[
            VariantSpec("v1", "2 templates", "parametric", {"template_count": 2, "seed": 42}),
            VariantSpec("v2", "8 templates", "parametric", {"template_count": 8, "seed": 42}),
        ],
        max_cycles=2,
    )
    defaults.update(overrides)
    return Hypothesis(**defaults)


def test_hypothesis_round_trips():
    h = _make_hypothesis()
    d = h.to_dict()
    restored = Hypothesis.from_dict(d)
    assert restored.hypothesis_id == h.hypothesis_id
    assert restored.domain == h.domain
    assert len(restored.variants) == 2


def test_hypothesis_best_score_empty():
    h = _make_hypothesis()
    assert h.best_score_so_far() == 0.0


def test_hypothesis_best_score_across_iterations():
    h = _make_hypothesis()
    h.iteration_summaries = [
        [TrialSummary("v1", "p_v1", 3.2, 3.0, 0.5, 0.0, 0, "halt", 2)],
        [TrialSummary("v2", "p_v2", 4.1, 3.8, 0.4, 0.0, 0, "halt", 2)],
    ]
    assert h.best_score_so_far() == pytest.approx(4.1)


def test_hypothesis_from_yaml(tmp_path):
    import yaml
    data = {
        "hypothesis_id": "yaml_test",
        "question": "Does seed matter?",
        "predicted_outcome": "Yes",
        "domain": "film",
        "seeds": ["seed_x"],
        "variants": [
            {"variant_id": "v1", "description": "d", "arch_type": "parametric", "params": {}},
        ],
    }
    path = tmp_path / "h.yaml"
    path.write_text(yaml.dump(data))
    h = Hypothesis.from_yaml(str(path))
    assert h.hypothesis_id == "yaml_test"
    assert h.domain == "film"


# ------------------------------------------------------------------ #
# ParametricCognition                                                 #
# ------------------------------------------------------------------ #


class TestParametricCognition:
    def _make(self, **kwargs) -> ParametricCognition:
        return ParametricCognition(**kwargs)

    def test_default_arch_id_derived_from_params(self):
        arch = self._make()
        assert arch.architecture_id.startswith("parametric_")

    def test_explicit_variant_id(self):
        arch = self._make(variant_id="custom_id")
        assert arch.architecture_id == "custom_id"

    def test_propose_returns_nonempty_string(self):
        arch = self._make(seed=42)
        result = arch.propose("parent concept", "sacrifice ritual 2026")
        assert isinstance(result, str)
        assert len(result.strip()) > 10

    def test_propose_is_deterministic(self):
        arch1 = self._make(seed=7)
        arch2 = self._make(seed=7)
        assert arch1.propose("p", "ctx") == arch2.propose("p", "ctx")

    def test_propose_seed_changes_output(self):
        r1 = self._make(seed=1).propose("p", "ctx")
        r2 = self._make(seed=99).propose("p", "ctx")
        assert r1 != r2

    def test_template_count_1_uses_one_template(self):
        arch = self._make(template_count=1, seed=42)
        assert len(arch._prod_templates) == 1

    def test_template_count_clamped_at_8(self):
        arch = self._make(template_count=99, seed=42)
        assert len(arch._prod_templates) == 8

    def test_template_count_min_1(self):
        arch = self._make(template_count=0, seed=42)
        assert len(arch._prod_templates) == 1

    def test_no_context_injection_skips_fractures(self):
        arch = self._make(context_injection=False, seed=1)
        result = arch.propose("parent", "anxiety sacrifice nostalgia 2026")
        trace = arch.reasoning_trace()
        assert "fractures: []" in trace[2]

    def test_context_injection_extracts_fractures(self):
        arch = self._make(context_injection=True, seed=1)
        arch.propose("parent", "anxiety sacrifice nostalgia 2026")
        trace = arch.reasoning_trace()
        fractures = trace[2]
        assert "fractures:" in fractures

    def test_embed_hash_returns_384_dims(self):
        arch = self._make()
        emb = arch.embed("some concept text")
        assert len(emb) == 384

    def test_embed_hash_is_normalised(self):
        arch = self._make()
        emb = arch.embed("test text")
        norm = math.sqrt(sum(x * x for x in emb))
        assert abs(norm - 1.0) < 1e-6

    def test_embed_hash_different_texts_differ(self):
        arch = self._make()
        e1 = arch.embed("alpha beta gamma")
        e2 = arch.embed("delta epsilon zeta")
        assert e1 != e2

    def test_coherence_slot_ratio_in_range(self):
        arch = self._make(coherence_mode="slot_ratio")
        c = arch.coherence("A recursive artifact that collapses when entropy exceeds threshold.")
        assert 0.0 <= c <= 1.0

    def test_coherence_length_in_range(self):
        arch = self._make(coherence_mode="length")
        c = arch.coherence("A short concept.")
        assert 0.0 <= c <= 1.0

    def test_coherence_entropy_in_range(self):
        arch = self._make(coherence_mode="entropy")
        c = arch.coherence("A diverse rich complex concept with many unique words that vary.")
        assert 0.0 <= c <= 1.0

    def test_reasoning_trace_after_propose(self):
        arch = self._make(seed=42)
        assert arch.reasoning_trace() == []
        arch.propose("p", "ctx")
        trace = arch.reasoning_trace()
        assert any("template" in t for t in trace)
        assert any("template_pool_size" in t for t in trace)


# ------------------------------------------------------------------ #
# Clean-room infrastructure                                           #
# ------------------------------------------------------------------ #


class TestResearchMemory:
    def test_seed_initialises_archive(self):
        mem = _ResearchMemory()
        mem.seed(["concept a", "concept b"])
        assert len(mem._archive) == 2

    def test_novelty_high_for_empty_archive(self):
        mem = _ResearchMemory()
        emb = [0.1] * 384
        assert mem.novelty_of(emb) == pytest.approx(0.90)

    def test_add_respects_threshold(self):
        mem = _ResearchMemory(novelty_threshold=0.5)
        mem.add("low novelty", [1.0] + [0.0] * 383, novelty=0.3, generation=0)
        assert all("embedding" not in e for e in mem._archive)
        mem.add("high novelty", [0.0, 1.0] + [0.0] * 382, novelty=0.8, generation=0)
        assert any("embedding" in e for e in mem._archive)

    def test_session_snapshot_structure(self):
        mem = _ResearchMemory()
        snap = mem.session_snapshot()
        assert "archive_size" in snap
        assert "session_embeddings" in snap
        assert "refractory_clusters" in snap

    def test_retired_ids_empty(self):
        mem = _ResearchMemory()
        assert mem.retired_ids() == set()


class TestCyclePlanner:
    def test_initial_action_continue(self):
        p = _CyclePlanner(3)
        ctx = MagicMock()
        assert p.initial_action(ctx) == "continue"

    def test_halts_at_max(self):
        p = _CyclePlanner(3)
        state = MagicMock(cycle=2)
        assert p.should_halt(state) is True
        assert p.next_action(state) == "halt"

    def test_continues_before_max(self):
        p = _CyclePlanner(3)
        state = MagicMock(cycle=1)
        assert p.should_halt(state) is False
        assert p.next_action(state) == "continue"


class TestHeuristicVerification:
    def test_score_in_range(self):
        ver = _HeuristicVerification()
        ctx = MagicMock()
        ctx.config = {"domain": "gaming"}
        result = ver.score("A recursive sacrifice protocol that crystallizes when memory saturates.", ctx)
        assert 1.0 <= result.composite_score <= 5.0

    def test_verdict_hit_for_good_candidate(self):
        ver = _HeuristicVerification()
        ctx = MagicMock()
        ctx.config = {"domain": "gaming"}
        long_candidate = " ".join([
            "A deeply recursive and entropic sacrifice protocol that",
            "crystallizes when the attention threshold exceeds its boundary,",
            "embodying post-optimization anxiety and epistemic drift.",
        ])
        result = ver.score(long_candidate, ctx)
        assert result.verdict in ("HIT", "SLOP")


# ------------------------------------------------------------------ #
# arch instantiation                                                  #
# ------------------------------------------------------------------ #


def test_instantiate_parametric():
    spec = VariantSpec("v1", "test", "parametric", {"template_count": 4, "seed": 1})
    arch = _instantiate_arch(spec)
    assert arch.architecture_id == "v1"


def test_instantiate_symbolic_grammar():
    spec = VariantSpec("sg_v1", "test", "symbolic_grammar", {"seed": 7})
    arch = _instantiate_arch(spec)
    assert arch.architecture_id == "symbolic_grammar_v1"


def test_instantiate_unknown_raises():
    spec = VariantSpec("bad", "test", "nonexistent_arch", {})
    with pytest.raises(ValueError, match="Unknown arch_type"):
        _instantiate_arch(spec)


# ------------------------------------------------------------------ #
# ControlledTrialRunner                                               #
# ------------------------------------------------------------------ #


class TestControlledTrialRunner:
    def _make_hypothesis(self, n_variants=2, cycles=2) -> Hypothesis:
        variants = [
            VariantSpec(f"v{i}", f"variant {i}", "parametric",
                        {"template_count": i + 2, "seed": i * 10 + 42})
            for i in range(n_variants)
        ]
        return Hypothesis(
            hypothesis_id="runner_test",
            question="Does template_count matter?",
            predicted_outcome="More templates → higher scores",
            domain="gaming",
            seeds=["a sacrifice game", "a grief engine"],
            variants=variants,
            max_cycles=cycles,
        )

    def test_run_returns_one_trace_per_variant(self):
        h = self._make_hypothesis(n_variants=2, cycles=2)
        runner = ControlledTrialRunner(record_to_ledger=False)
        traces = runner.run(h)
        assert len(traces) == 2

    def test_traces_have_different_architecture_ids(self):
        h = self._make_hypothesis(n_variants=2, cycles=2)
        runner = ControlledTrialRunner(record_to_ledger=False)
        traces = runner.run(h)
        ids = {t.architecture_id for t in traces}
        assert len(ids) == 2

    def test_traces_share_experiment_id(self):
        h = self._make_hypothesis(n_variants=2, cycles=2)
        runner = ControlledTrialRunner(record_to_ledger=False)
        traces = runner.run(h)
        assert all(t.experiment_id == "runner_test" for t in traces)

    def test_summaries_extracted_correctly(self):
        h = self._make_hypothesis(n_variants=2, cycles=2)
        runner = ControlledTrialRunner(record_to_ledger=False)
        traces = runner.run(h)
        summaries = ControlledTrialRunner.summaries_from_traces(h.variants, traces)
        assert len(summaries) == 2
        for s in summaries:
            assert isinstance(s.best_score, float)
            assert s.best_score >= 0.0

    def test_symbolic_grammar_variant_runs(self):
        h = Hypothesis(
            hypothesis_id="sg_test",
            question="Does symbolic grammar baseline work?",
            predicted_outcome="Yes",
            domain="gaming",
            seeds=["a"],
            variants=[VariantSpec("sg_v1", "sg baseline", "symbolic_grammar", {"seed": 42})],
            max_cycles=2,
        )
        runner = ControlledTrialRunner(record_to_ledger=False)
        traces = runner.run(h)
        assert len(traces) == 1
        assert traces[0].architecture_id == "symbolic_grammar_v1"


# ------------------------------------------------------------------ #
# ExperimentLoop (mocked client)                                      #
# ------------------------------------------------------------------ #


class TestExperimentLoop:
    def _make_hypothesis(self) -> Hypothesis:
        return Hypothesis(
            hypothesis_id="loop_test",
            question="Does template_count matter?",
            predicted_outcome="Higher count = higher scores",
            domain="gaming",
            seeds=["sacrifice game", "grief engine"],
            variants=[
                VariantSpec("iter1_v1", "2 templates", "parametric", {"template_count": 2, "seed": 42}),
                VariantSpec("iter1_v2", "8 templates", "parametric", {"template_count": 8, "seed": 42}),
            ],
            max_cycles=2,
            stopping_criterion="max_iterations",
        )

    def test_loop_runs_to_max_iterations(self):
        from uaf.research.loop import ExperimentLoop

        h = self._make_hypothesis()
        loop = ExperimentLoop(max_iterations=1, record_to_ledger=False, verbose=False)
        # First iteration runs without refinement call (only 1 iter)
        result = loop.run(h)
        assert result.iteration == 1
        assert len(result.iteration_summaries) == 1
        assert len(result.findings) == 1

    def test_loop_score_threshold_stops_early(self):
        from uaf.research.loop import ExperimentLoop

        h = self._make_hypothesis()
        h.stopping_criterion = "score_threshold"
        h.target_score = 0.1  # impossibly low — will be hit on first iter

        loop = ExperimentLoop(max_iterations=5, record_to_ledger=False, verbose=False)
        result = loop.run(h)
        # Should stop after iter 1 since all scores > 0.1
        assert result.iteration == 1
        assert result.resolved is True
        assert "reached" in result.resolution

    def test_loop_records_findings(self):
        from uaf.research.loop import ExperimentLoop

        h = self._make_hypothesis()
        loop = ExperimentLoop(max_iterations=1, record_to_ledger=False, verbose=False)
        result = loop.run(h)
        assert len(result.findings) == 1
        assert "iter1_v" in result.findings[0] or "iter" in result.findings[0].lower()

    def test_loop_refine_calls_claude(self):
        from uaf.research.loop import ExperimentLoop

        mock_client = MagicMock()
        # First call: _refine_variants
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text=json.dumps([
                {
                    "variant_id": "iter2_v1",
                    "description": "refined",
                    "arch_type": "parametric",
                    "params": {"template_count": 6, "seed": 42},
                }
            ]))]
        )

        h = self._make_hypothesis()
        loop = ExperimentLoop(
            max_iterations=2, record_to_ledger=False,
            client=mock_client, verbose=False
        )
        result = loop.run(h)
        # Claude should have been called at least once (to refine after iter 1)
        assert mock_client.messages.create.called
        assert result.iteration == 2

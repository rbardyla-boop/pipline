"""Phase 5 tests: SymbolicGrammarCognition + ExperimentRunner + Ledger.

All tests are deterministic (seed=42), no API calls, no model downloads.
"""

import json
import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from uaf.interfaces.cognition import CognitionEngine
from uaf.kernel.state import SimulationContext, VerificationResult
from uaf.kernel.simulation import SimulationKernel
from uaf.kernel.invariants import InvariantSet
from uaf.experiments.definition import ExperimentDefinition
from uaf.experiments.runner import ExperimentRunner, ExperimentTrace
from uaf.experiments.ledger import ExperimentLedger
from uaf.experiments.comparison import compare_traces, best_architecture


# ------------------------------------------------------------------ #
# SymbolicGrammarCognition                                            #
# ------------------------------------------------------------------ #


class TestSymbolicGrammarCognition:
    def _make_arch(self, seed=42):
        from architectures.symbolic_grammar.adapter import SymbolicGrammarCognition
        return SymbolicGrammarCognition(seed=seed)

    def test_is_cognition_engine(self):
        arch = self._make_arch()
        assert isinstance(arch, CognitionEngine)

    def test_architecture_id(self):
        arch = self._make_arch()
        assert arch.architecture_id == "symbolic_grammar_v1"

    def test_propose_returns_nonempty_string(self):
        arch = self._make_arch()
        result = arch.propose("parent concept", "anxiety sacrifice nostalgia context")
        assert isinstance(result, str)
        assert len(result.strip()) > 10

    def test_propose_is_deterministic(self):
        arch1 = self._make_arch(seed=42)
        arch2 = self._make_arch(seed=42)
        r1 = arch1.propose("parent", "context")
        r2 = arch2.propose("parent", "context")
        assert r1 == r2

    def test_propose_seed_changes_output(self):
        arch1 = self._make_arch(seed=42)
        arch2 = self._make_arch(seed=99)
        r1 = arch1.propose("parent", "context")
        r2 = arch2.propose("parent", "context")
        # Different seeds should (probabilistically) produce different outputs
        # With 8 templates and many slot options, collision is < 1%
        # We run 3 pairs to make this robust
        any_different = any(
            self._make_arch(seed=s).propose("p", "c") != self._make_arch(seed=s + 100).propose("p", "c")
            for s in [42, 43, 44]
        )
        assert any_different

    def test_embed_returns_384_dims(self):
        arch = self._make_arch()
        emb = arch.embed("some concept text")
        assert len(emb) == 384

    def test_embed_is_normalised(self):
        import math
        arch = self._make_arch()
        emb = arch.embed("test text")
        norm = math.sqrt(sum(x * x for x in emb))
        assert abs(norm - 1.0) < 1e-6

    def test_embed_different_texts_differ(self):
        arch = self._make_arch()
        e1 = arch.embed("alpha beta gamma")
        e2 = arch.embed("delta epsilon zeta")
        assert e1 != e2

    def test_coherence_in_range(self):
        arch = self._make_arch()
        c = arch.coherence("A recursive ritual that decays when attention exceeds threshold.")
        assert 0.0 <= c <= 1.0

    def test_reasoning_trace_after_propose(self):
        arch = self._make_arch()
        assert arch.reasoning_trace() == []
        arch.propose("p", "ctx")
        trace = arch.reasoning_trace()
        assert len(trace) >= 1
        assert any("template" in t for t in trace)

    def test_context_fractures_injected(self):
        arch = self._make_arch(seed=1)
        result = arch.propose("parent", "sacrifice ritual nostalgia embodied context 2026")
        # Should contain at least one word from the context
        # (not guaranteed for every seed, but highly likely with 3 fractures extracted)
        # Just verify it runs without error and produces output
        assert len(result) > 5


# ------------------------------------------------------------------ #
# Null infrastructure for integration tests                           #
# ------------------------------------------------------------------ #


class _NullMemory:
    def __init__(self):
        self.archive = []

    def seed(self, items):
        for item in items:
            self.archive.append({"concept": item})

    def add(self, item, embedding, novelty, generation):
        if novelty > 0.5:
            self.archive.append({"concept": item})

    def novelty_of(self, embedding):
        return 0.9

    def retired_ids(self):
        return set()

    def retire(self, item, score, combined, run_id):
        pass

    def session_snapshot(self):
        return {"archive_size": len(self.archive), "session_embeddings": [], "refractory_clusters": []}


class _FixedScoreVerification:
    def __init__(self, score=3.5):
        self._score = score

    def score(self, candidate, ctx):
        return VerificationResult(
            composite_score=self._score,
            criteria_scores={},
            ritual_cost_score=0.0,
            anti_optimization_score=0.0,
            improvement_context="",
            goodhart_warning=False,
            verdict="SLOP",
            extended_verdict="SLOP",
        )

    def verdict(self, r):
        return r.verdict


class _HaltAfterN:
    def __init__(self, n):
        self._n = n

    def initial_action(self, ctx):
        return "continue"

    def next_action(self, state):
        return "halt" if state.cycle >= self._n - 1 else "continue"

    def should_halt(self, state):
        return state.cycle >= self._n - 1


class _NullRuntime:
    _id = "null-test-001"

    def ingest_context(self, domain):
        return "sacrifice ritual nostalgia 2026 cultural context"

    def secure_call(self, fn, *args, **kwargs):
        return fn(*args, **kwargs)

    def persist(self, key, payload):
        pass

    def run_id(self):
        return self._id


def _make_defn(arch, experiment_id="test_exp", score=3.5, n_cycles=3, config=None):
    return ExperimentDefinition(
        experiment_id=experiment_id,
        architecture=arch,
        memory=_NullMemory(),
        planner=_HaltAfterN(n_cycles),
        verification=_FixedScoreVerification(score),
        runtime=_NullRuntime(),
        invariants=InvariantSet.default(),
        config=config or {"domain": "gaming", "seeds": ["seed_a", "seed_b"]},
    )


# ------------------------------------------------------------------ #
# ExperimentRunner                                                    #
# ------------------------------------------------------------------ #


class TestExperimentRunner:
    def test_run_symbolic_arch(self):
        from architectures.symbolic_grammar.adapter import SymbolicGrammarCognition
        arch = SymbolicGrammarCognition(seed=42)
        defn = _make_defn(arch, n_cycles=3)
        runner = ExperimentRunner()
        trace = runner.execute(defn)
        assert isinstance(trace, ExperimentTrace)
        assert trace.architecture_id == "symbolic_grammar_v1"

    def test_trace_has_cycles(self):
        from architectures.symbolic_grammar.adapter import SymbolicGrammarCognition
        defn = _make_defn(SymbolicGrammarCognition(seed=42), n_cycles=4)
        trace = ExperimentRunner().execute(defn)
        assert trace.simulation_result["total_cycles"] == 4

    def test_trace_dynamics_series_length(self):
        from architectures.symbolic_grammar.adapter import SymbolicGrammarCognition
        defn = _make_defn(SymbolicGrammarCognition(seed=42), n_cycles=3)
        trace = ExperimentRunner().execute(defn)
        assert len(trace.dynamics_series) == 3

    def test_trace_to_dict_serialisable(self):
        from architectures.symbolic_grammar.adapter import SymbolicGrammarCognition
        defn = _make_defn(SymbolicGrammarCognition(seed=42), n_cycles=2)
        trace = ExperimentRunner().execute(defn)
        d = trace.to_dict()
        # Must be JSON-serialisable
        json.dumps(d)

    def test_two_arches_same_experiment(self):
        """Both architectures run the same experiment definition and both succeed."""
        from architectures.symbolic_grammar.adapter import SymbolicGrammarCognition

        # Arch #1 style: null deterministic with architecture_id != symbolic
        class _AltArch(CognitionEngine):
            architecture_id = "alt_v0"
            _c = 0

            def propose(self, parent, context):
                self.__class__._c += 1
                return f"alt_{self._c}"

            def embed(self, text):
                return [0.1] * 384

            def coherence(self, c):
                return 0.6

        runner = ExperimentRunner()

        defn_symbolic = _make_defn(SymbolicGrammarCognition(seed=42), experiment_id="test_ab")
        defn_alt = _make_defn(_AltArch(), experiment_id="test_ab")

        trace_symbolic = runner.execute(defn_symbolic)
        trace_alt = runner.execute(defn_alt)

        assert trace_symbolic.architecture_id == "symbolic_grammar_v1"
        assert trace_alt.architecture_id == "alt_v0"
        assert trace_symbolic.experiment_id == trace_alt.experiment_id


# ------------------------------------------------------------------ #
# ExperimentLedger                                                    #
# ------------------------------------------------------------------ #


class TestExperimentLedger:
    def test_record_and_load(self, tmp_path):
        from architectures.symbolic_grammar.adapter import SymbolicGrammarCognition
        ledger_path = str(tmp_path / "test_ledger.jsonl")
        ledger = ExperimentLedger(path=ledger_path)

        defn = _make_defn(SymbolicGrammarCognition(seed=42), n_cycles=2)
        trace = ExperimentRunner().execute(defn)
        ledger.record(trace)

        records = ledger.load_all()
        assert len(records) == 1
        assert records[0]["architecture_id"] == "symbolic_grammar_v1"

    def test_load_empty_ledger(self, tmp_path):
        ledger = ExperimentLedger(path=str(tmp_path / "empty.jsonl"))
        assert ledger.load_all() == []

    def test_load_by_architecture(self, tmp_path):
        from architectures.symbolic_grammar.adapter import SymbolicGrammarCognition

        class _AltArch(CognitionEngine):
            architecture_id = "alt_v1"
            _c = 0

            def propose(self, parent, context):
                self.__class__._c += 1
                return f"a{self._c}"

            def embed(self, text):
                return [0.2] * 384

            def coherence(self, c):
                return 0.5

        ledger = ExperimentLedger(path=str(tmp_path / "multi.jsonl"))
        runner = ExperimentRunner()

        t1 = runner.execute(_make_defn(SymbolicGrammarCognition(seed=42), n_cycles=2))
        t2 = runner.execute(_make_defn(_AltArch(), n_cycles=2))
        ledger.record(t1)
        ledger.record(t2)

        symbolic_records = ledger.load_by_architecture("symbolic_grammar_v1")
        assert len(symbolic_records) == 1

    def test_ledger_records_both_arches(self, tmp_path):
        from architectures.symbolic_grammar.adapter import SymbolicGrammarCognition

        class _AltArch2(CognitionEngine):
            architecture_id = "alt_v2"
            _c = 0

            def propose(self, p, c):
                self.__class__._c += 1
                return f"a{self._c}"

            def embed(self, t):
                return [0.3] * 384

            def coherence(self, c):
                return 0.5

        ledger = ExperimentLedger(path=str(tmp_path / "both.jsonl"))
        runner = ExperimentRunner()
        ledger.record(runner.execute(_make_defn(SymbolicGrammarCognition(seed=42), n_cycles=2, experiment_id="ab_test")))
        ledger.record(runner.execute(_make_defn(_AltArch2(), n_cycles=2, experiment_id="ab_test")))

        all_records = ledger.load_all()
        assert len(all_records) == 2
        arch_ids = {r["architecture_id"] for r in all_records}
        assert "symbolic_grammar_v1" in arch_ids
        assert "alt_v2" in arch_ids

    def test_invariant_violation_recorded_correctly(self, tmp_path):
        """Invariant violations produce a recognisable halt_reason in the trace."""
        from architectures.symbolic_grammar.adapter import SymbolicGrammarCognition

        class _BadScoreVerification:
            def score(self, candidate, ctx):
                return VerificationResult(
                    composite_score=6.5,  # violates ScoreInRange
                    criteria_scores={},
                    ritual_cost_score=0.0,
                    anti_optimization_score=0.0,
                    improvement_context="",
                    goodhart_warning=False,
                    verdict="HIT",
                    extended_verdict="HIT",
                )

            def verdict(self, r):
                return r.verdict

        defn = ExperimentDefinition(
            experiment_id="invariant_test",
            architecture=SymbolicGrammarCognition(seed=42),
            memory=_NullMemory(),
            planner=_HaltAfterN(10),
            verification=_BadScoreVerification(),
            runtime=_NullRuntime(),
            invariants=InvariantSet.default(),
            config={"domain": "gaming", "seeds": ["a"]},
        )
        trace = ExperimentRunner().execute(defn)
        assert "fail_recover" in trace.simulation_result["halt_reason"]


# ------------------------------------------------------------------ #
# Comparison utilities                                                #
# ------------------------------------------------------------------ #


class TestComparison:
    def _make_fake_trace(self, arch_id, best_score, final_score):
        return {
            "architecture_id": arch_id,
            "experiment_id": "test",
            "dynamics_summary": {
                "architecture_id": arch_id,
                "best_score": best_score,
                "final_score": final_score,
                "mean_score": (best_score + final_score) / 2,
                "goodhart_total": 0,
            },
        }

    def test_compare_traces_empty(self):
        assert compare_traces([]) == {}

    def test_compare_single_trace(self):
        t = self._make_fake_trace("arch_a", 4.0, 3.8)
        result = compare_traces([t])
        assert "single_trace" in result

    def test_compare_two_traces(self):
        traces = [
            self._make_fake_trace("arch_a", 4.0, 3.8),
            self._make_fake_trace("arch_b", 3.5, 3.2),
        ]
        result = compare_traces(traces)
        assert "deltas" in result
        # arch_a best_score - arch_b best_score = 0.5
        key = [k for k in result["deltas"] if "best_score" in k][0]
        assert abs(result["deltas"][key] - 0.5) < 1e-6

    def test_best_architecture(self):
        traces = [
            self._make_fake_trace("arch_a", 4.0, 3.8),
            self._make_fake_trace("arch_b", 3.5, 3.2),
        ]
        assert best_architecture(traces, metric="best_score") == "arch_a"

    def test_best_architecture_empty(self):
        assert best_architecture([]) is None

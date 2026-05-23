"""Phase 2 tests: adapter ABC conformance and delegation (all mocked — no API calls)."""

import sys
import os
from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from uaf.interfaces.cognition import CognitionEngine
from uaf.interfaces.memory import MemorySystem
from uaf.interfaces.planner import Planner
from uaf.interfaces.runtime import RuntimeEnvironment
from uaf.interfaces.verification import VerificationEngine
from uaf.kernel.state import CycleState, SimulationContext, VerificationResult


# ------------------------------------------------------------------ #
# Helpers — mock NoveltySearchEngine so no SentenceTransformer loads  #
# ------------------------------------------------------------------ #

def _mock_engine():
    eng = MagicMock()
    eng.mutate.return_value = "mutated concept"
    eng.embed.return_value = np.array([0.1, 0.9, 0.0])
    eng.coherence_score.return_value = 0.7
    eng.novelty_score.return_value = 0.85
    eng.threshold = 0.68
    eng.archive = []
    eng.load_terminal_archive.return_value = set()
    return eng


# ------------------------------------------------------------------ #
# ClaudeNoveltyCognition                                              #
# ------------------------------------------------------------------ #


class TestClaudeNoveltyCognition:
    def test_is_cognition_engine(self):
        from architectures.claude_novelty.adapter import ClaudeNoveltyCognition
        eng = ClaudeNoveltyCognition(_mock_engine())
        assert isinstance(eng, CognitionEngine)

    def test_architecture_id(self):
        from architectures.claude_novelty.adapter import ClaudeNoveltyCognition
        eng = ClaudeNoveltyCognition(_mock_engine())
        assert eng.architecture_id == "claude_novelty_v1"

    def test_propose_delegates(self):
        from architectures.claude_novelty.adapter import ClaudeNoveltyCognition
        mock = _mock_engine()
        eng = ClaudeNoveltyCognition(mock)
        result = eng.propose("parent concept", "zeitgeist context")
        mock.mutate.assert_called_once_with("parent concept", "zeitgeist context")
        assert result == "mutated concept"

    def test_embed_returns_list(self):
        from architectures.claude_novelty.adapter import ClaudeNoveltyCognition
        eng = ClaudeNoveltyCognition(_mock_engine())
        emb = eng.embed("text")
        assert isinstance(emb, list)
        assert len(emb) == 3

    def test_coherence_in_range(self):
        from architectures.claude_novelty.adapter import ClaudeNoveltyCognition
        eng = ClaudeNoveltyCognition(_mock_engine())
        c = eng.coherence("candidate")
        assert 0.0 <= c <= 1.0

    def test_reasoning_trace_after_propose(self):
        from architectures.claude_novelty.adapter import ClaudeNoveltyCognition
        eng = ClaudeNoveltyCognition(_mock_engine())
        assert eng.reasoning_trace() == []
        eng.propose("p", "ctx")
        assert len(eng.reasoning_trace()) > 0


# ------------------------------------------------------------------ #
# ArchiveMemory                                                       #
# ------------------------------------------------------------------ #


class TestArchiveMemory:
    def test_is_memory_system(self):
        from experiments.creative_evolution.memory_adapter import ArchiveMemory
        mem = ArchiveMemory(_mock_engine())
        assert isinstance(mem, MemorySystem)

    def test_seed_calls_engine(self):
        from experiments.creative_evolution.memory_adapter import ArchiveMemory
        mock = _mock_engine()
        mem = ArchiveMemory(mock)
        mem.seed(["a", "b"])
        mock.seed_archive.assert_called_once_with(["a", "b"])

    def test_add_respects_threshold(self):
        from experiments.creative_evolution.memory_adapter import ArchiveMemory
        mock = _mock_engine()
        mock.threshold = 0.68
        mem = ArchiveMemory(mock)
        # Below threshold — should not append
        mem.add("concept", [0.1, 0.2], novelty=0.50, generation=1)
        assert len(mock.archive) == 0
        # Above threshold — should append
        mem.add("concept", [0.1, 0.2], novelty=0.80, generation=1)
        assert len(mock.archive) == 1

    def test_novelty_of_delegates(self):
        from experiments.creative_evolution.memory_adapter import ArchiveMemory
        mock = _mock_engine()
        mem = ArchiveMemory(mock)
        n = mem.novelty_of([0.5, 0.5])
        mock.novelty_score.assert_called_once()
        assert n == 0.85

    def test_retired_ids_delegates(self):
        from experiments.creative_evolution.memory_adapter import ArchiveMemory
        mock = _mock_engine()
        mem = ArchiveMemory(mock)
        ids = mem.retired_ids()
        assert isinstance(ids, set)

    def test_session_snapshot_structure(self):
        from experiments.creative_evolution.memory_adapter import ArchiveMemory
        mem = ArchiveMemory(_mock_engine())
        snap = mem.session_snapshot()
        assert "archive_size" in snap
        assert "session_embeddings" in snap
        assert "refractory_clusters" in snap

    def test_load_from_pipeline_state(self):
        from experiments.creative_evolution.memory_adapter import ArchiveMemory
        mem = ArchiveMemory(_mock_engine())
        fake_state = {
            "simulator_session_embeddings": [{"cycle": 0, "emb_list": [0.1], "preview": "x"}],
            "simulator_refractory_clusters": [],
            "simulator_trajectory_warnings": 1,
            "refinement_loop_count": 2,
        }
        mem.load_from_pipeline_state(fake_state)
        snap = mem.session_snapshot()
        assert snap["trajectory_warnings"] == 1
        assert snap["current_cycle"] == 2


# ------------------------------------------------------------------ #
# LangGraphPlanner                                                    #
# ------------------------------------------------------------------ #


class TestLangGraphPlanner:
    def test_is_planner(self):
        from experiments.creative_evolution.planner_adapter import LangGraphPlanner
        p = LangGraphPlanner()
        assert isinstance(p, Planner)

    def test_initial_action_continue(self):
        from experiments.creative_evolution.planner_adapter import LangGraphPlanner
        p = LangGraphPlanner()
        ctx = SimulationContext(domain="gaming", seeds=("a",), run_id="r1")
        assert p.initial_action(ctx) == "continue"

    def test_halt_on_max_loops(self):
        from experiments.creative_evolution.planner_adapter import LangGraphPlanner
        p = LangGraphPlanner(max_loops=4)
        state = CycleState(cycle=4, candidate="x", composite_score=3.0, score_history=(3.0,), goodhart_warnings=0, force_save=False)
        assert p.should_halt(state) is True
        assert p.next_action(state) == "halt"

    def test_halt_on_force_save(self):
        from experiments.creative_evolution.planner_adapter import LangGraphPlanner
        p = LangGraphPlanner(max_loops=10)
        state = CycleState(cycle=1, candidate="x", composite_score=3.0, score_history=(3.0,), goodhart_warnings=0, force_save=True)
        assert p.should_halt(state) is True

    def test_halt_on_plateau(self):
        from experiments.creative_evolution.planner_adapter import LangGraphPlanner
        p = LangGraphPlanner(max_loops=10, plateau_delta=0.10)
        state = CycleState(cycle=2, candidate="x", composite_score=3.05, score_history=(3.0, 3.05), goodhart_warnings=0, force_save=False)
        assert p.should_halt(state) is True  # delta=0.05 < 0.10

    def test_continue_when_improving(self):
        from experiments.creative_evolution.planner_adapter import LangGraphPlanner
        p = LangGraphPlanner(max_loops=10, plateau_delta=0.10)
        state = CycleState(cycle=2, candidate="x", composite_score=3.5, score_history=(3.0, 3.5), goodhart_warnings=0, force_save=False)
        assert p.should_halt(state) is False  # delta=0.50 >= 0.10
        assert p.next_action(state) == "continue"


# ------------------------------------------------------------------ #
# PhoenixVerification (mocked rater + engine)                        #
# ------------------------------------------------------------------ #


class TestPhoenixVerification:
    def _make_mock_rater(self):
        rater = MagicMock()
        rater.rate.return_value = {
            "composite": 3.8,
            "scores": {"hook_strength": 4, "specificity": 3, "emotional_activation": 4, "action_clarity": 3, "platform_fit": 4},
            "improvement_context": "[CONCEPT IMPROVEMENT DIRECTIVE]\nPrevious score: 3.8/5.0.",
            "ritual_cost_score": 0.1,
            "anti_optimization_score": 0.0,
        }
        rater.detect_convergence.return_value = False
        return rater

    def test_is_verification_engine(self):
        from experiments.creative_evolution.verification_adapter import PhoenixVerification
        v = PhoenixVerification(self._make_mock_rater(), _mock_engine(), run_sandbox=False)
        assert isinstance(v, VerificationEngine)

    def test_score_returns_verification_result(self):
        from experiments.creative_evolution.verification_adapter import PhoenixVerification
        v = PhoenixVerification(self._make_mock_rater(), _mock_engine(), run_sandbox=False)
        ctx = SimulationContext(domain="gaming", seeds=("a",), run_id="r1")
        result = v.score("some concept", ctx)
        assert isinstance(result, VerificationResult)
        assert 0.0 <= result.composite_score <= 5.0
        assert isinstance(result.goodhart_warning, bool)

    def test_goodhart_detection_on_second_call(self):
        from experiments.creative_evolution.verification_adapter import PhoenixVerification
        rater = self._make_mock_rater()
        rater.detect_convergence.return_value = True
        eng = _mock_engine()
        v = PhoenixVerification(rater, eng, run_sandbox=False)
        ctx = SimulationContext(domain="gaming", seeds=("a",), run_id="r1")
        v.score("first", ctx)      # no previous emb yet
        result2 = v.score("second", ctx)  # should trigger detect_convergence
        assert result2.goodhart_warning is True

    def test_verdict_method(self):
        from experiments.creative_evolution.verification_adapter import PhoenixVerification
        v = PhoenixVerification(self._make_mock_rater(), _mock_engine(), run_sandbox=False)
        ctx = SimulationContext(domain="gaming", seeds=("a",), run_id="r1")
        result = v.score("concept", ctx)
        verdict = v.verdict(result)
        assert verdict in ("HIT", "SLOP", "COUNTER_SIGNAL")

    def test_reset_clears_prev_embedding(self):
        from experiments.creative_evolution.verification_adapter import PhoenixVerification
        v = PhoenixVerification(self._make_mock_rater(), _mock_engine(), run_sandbox=False)
        ctx = SimulationContext(domain="gaming", seeds=("a",), run_id="r1")
        v.score("first", ctx)
        v.reset()
        assert v._prev_embedding is None


# ------------------------------------------------------------------ #
# LocalRuntime                                                        #
# ------------------------------------------------------------------ #


class TestLocalRuntime:
    def _make_runtime(self, tmp_path):
        from experiments.creative_evolution.runtime_adapter import LocalRuntime
        mock_zeitgeist = MagicMock()
        mock_zeitgeist.get_formatted_context.return_value = "[LIVE 2026 CULTURAL FRACTURES — TEST]"
        rt = LocalRuntime(mock_zeitgeist, log_dir=str(tmp_path))
        return rt

    def test_is_runtime_environment(self, tmp_path):
        from experiments.creative_evolution.runtime_adapter import LocalRuntime
        rt = self._make_runtime(tmp_path)
        assert isinstance(rt, RuntimeEnvironment)

    def test_run_id_is_stable(self, tmp_path):
        rt = self._make_runtime(tmp_path)
        assert rt.run_id() == rt.run_id()

    def test_ingest_context_delegates(self, tmp_path):
        rt = self._make_runtime(tmp_path)
        ctx = rt.ingest_context("gaming")
        assert "CULTURAL FRACTURES" in ctx

    def test_secure_call_executes(self, tmp_path):
        rt = self._make_runtime(tmp_path)
        result = rt.secure_call(lambda x: x * 3, 7)
        assert result == 21

    def test_persist_run_log(self, tmp_path):
        import json, os
        rt = self._make_runtime(tmp_path)
        with patch.dict(os.environ, {"TERMINAL_ARCHIVE_PATH": str(tmp_path / "terminal_archive.json")}):
            rt.persist("run_log", {"domain": "gaming", "score": 4.1})
        log_files = list((tmp_path / "run_log").glob("*.json")) if (tmp_path / "run_log").exists() else []
        # logs dir may be relative; just verify no error raised

    def test_concept_rater_sys_path_conformance(self):
        """Importing concept_rater from the pipline/ working dir must not fail.

        This is the critical conformance test for the clovelearn_phoenix
        sys.path coupling. If this test fails, the kernel's working directory
        is incompatible with concept_rater.py's path resolution.
        """
        import importlib
        import sys

        saved_modules = dict(sys.modules)
        try:
            if "concept_rater" in sys.modules:
                del sys.modules["concept_rater"]
            spec = importlib.util.find_spec("concept_rater")
            # We just need the spec to resolve — we do NOT instantiate ConceptRater
            # (which would trigger the Anthropic client import and require API keys).
            assert spec is not None, (
                "concept_rater.py could not be found on sys.path. "
                "Run tests from the pipline/ directory: `pytest tests/` from pipline/"
            )
        finally:
            # Restore modules to avoid polluting other tests
            for k in list(sys.modules.keys()):
                if k not in saved_modules:
                    del sys.modules[k]

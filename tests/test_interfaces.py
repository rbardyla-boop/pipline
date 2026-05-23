"""Phase 1 tests: ABC conformance and frozen state type behaviour."""

import pytest

from uaf.interfaces.cognition import CognitionEngine
from uaf.interfaces.memory import MemorySystem
from uaf.interfaces.planner import Planner
from uaf.interfaces.runtime import RuntimeEnvironment
from uaf.interfaces.verification import VerificationEngine
from uaf.kernel.state import CycleState, SimulationContext, VerificationResult


# ------------------------------------------------------------------ #
# Helpers: concrete minimal subclasses (one per ABC)                  #
# ------------------------------------------------------------------ #


class _MinimalCognition(CognitionEngine):
    architecture_id = "test_v0"

    def propose(self, parent, context):
        return parent + "_mutated"

    def embed(self, text):
        return [0.0, 1.0, 0.0]

    def coherence(self, candidate):
        return 0.5


class _MinimalMemory(MemorySystem):
    def seed(self, items):
        pass

    def add(self, item, embedding, novelty, generation):
        pass

    def novelty_of(self, embedding):
        return 1.0

    def retired_ids(self):
        return set()

    def retire(self, item, score, combined, run_id):
        pass

    def session_snapshot(self):
        return {"archive_size": 0, "session_embeddings": [], "refractory_clusters": []}


class _MinimalPlanner(Planner):
    def initial_action(self, ctx):
        return "continue"

    def next_action(self, state):
        return "halt" if self.should_halt(state) else "continue"

    def should_halt(self, state):
        return state.cycle >= 4


class _MinimalVerification(VerificationEngine):
    def score(self, candidate, ctx):
        return VerificationResult(
            composite_score=3.5,
            criteria_scores={},
            ritual_cost_score=0.1,
            anti_optimization_score=0.0,
            improvement_context="",
            goodhart_warning=False,
            verdict="SLOP",
            extended_verdict="SLOP",
        )

    def verdict(self, result):
        return result.verdict


class _MinimalRuntime(RuntimeEnvironment):
    def ingest_context(self, domain):
        return f"context for {domain}"

    def secure_call(self, fn, *args, **kwargs):
        return fn(*args, **kwargs)

    def persist(self, key, payload):
        pass

    def run_id(self):
        return "test-run-001"


# ------------------------------------------------------------------ #
# ABC — cannot instantiate directly                                    #
# ------------------------------------------------------------------ #


def test_cognition_engine_is_abstract():
    with pytest.raises(TypeError):
        CognitionEngine()  # type: ignore[abstract]


def test_memory_system_is_abstract():
    with pytest.raises(TypeError):
        MemorySystem()  # type: ignore[abstract]


def test_planner_is_abstract():
    with pytest.raises(TypeError):
        Planner()  # type: ignore[abstract]


def test_verification_engine_is_abstract():
    with pytest.raises(TypeError):
        VerificationEngine()  # type: ignore[abstract]


def test_runtime_environment_is_abstract():
    with pytest.raises(TypeError):
        RuntimeEnvironment()  # type: ignore[abstract]


# ------------------------------------------------------------------ #
# Concrete subclasses satisfy the contracts                           #
# ------------------------------------------------------------------ #


def test_cognition_minimal_impl():
    eng = _MinimalCognition()
    assert eng.propose("foo", "ctx") == "foo_mutated"
    assert len(eng.embed("foo")) == 3
    assert 0.0 <= eng.coherence("foo") <= 1.0
    assert eng.architecture_id == "test_v0"
    assert eng.reasoning_trace() == []
    assert eng.uncertainty_map() == {}


def test_memory_minimal_impl():
    mem = _MinimalMemory()
    mem.seed(["a", "b"])
    mem.add("c", [0.1, 0.2], 0.9, 1)
    assert mem.novelty_of([1.0, 0.0]) == 1.0
    assert isinstance(mem.retired_ids(), set)
    snap = mem.session_snapshot()
    assert "archive_size" in snap
    assert "session_embeddings" in snap
    assert "refractory_clusters" in snap


def test_planner_minimal_impl():
    planner = _MinimalPlanner()
    ctx = SimulationContext(domain="test", seeds=("a",), run_id="r1")
    assert planner.initial_action(ctx) == "continue"

    state_early = CycleState(cycle=2, candidate="x", composite_score=3.0, score_history=(3.0,), goodhart_warnings=0, force_save=False)
    assert planner.next_action(state_early) == "continue"

    state_late = CycleState(cycle=4, candidate="x", composite_score=3.5, score_history=(3.0, 3.5), goodhart_warnings=0, force_save=False)
    assert planner.next_action(state_late) == "halt"


def test_verification_minimal_impl():
    ver = _MinimalVerification()
    ctx = SimulationContext(domain="test", seeds=("a",), run_id="r1")
    result = ver.score("some concept", ctx)
    assert isinstance(result, VerificationResult)
    assert 0.0 <= result.composite_score <= 5.0
    assert ver.verdict(result) in ("HIT", "SLOP", "COUNTER_SIGNAL")


def test_runtime_minimal_impl():
    rt = _MinimalRuntime()
    assert "test" in rt.ingest_context("test")
    assert rt.secure_call(lambda x: x * 2, 21) == 42
    rt.persist("run_log", {"data": 1})
    assert rt.run_id() == "test-run-001"


# ------------------------------------------------------------------ #
# Frozen state types                                                  #
# ------------------------------------------------------------------ #


def test_simulation_context_is_frozen():
    ctx = SimulationContext(domain="gaming", seeds=("a", "b"), run_id="r1")
    with pytest.raises((AttributeError, TypeError)):
        ctx.domain = "other"  # type: ignore[misc]


def test_cycle_state_is_frozen():
    state = CycleState(cycle=1, candidate="x", composite_score=3.0, score_history=(3.0,), goodhart_warnings=0, force_save=False)
    with pytest.raises((AttributeError, TypeError)):
        state.cycle = 2  # type: ignore[misc]


def test_verification_result_is_frozen():
    vr = VerificationResult(
        composite_score=4.0,
        criteria_scores={},
        ritual_cost_score=0.2,
        anti_optimization_score=0.1,
        improvement_context="",
        goodhart_warning=False,
        verdict="HIT",
        extended_verdict="HIT",
    )
    with pytest.raises((AttributeError, TypeError)):
        vr.composite_score = 5.0  # type: ignore[misc]


def test_cycle_state_plateau_delta():
    state_no_history = CycleState(cycle=0, candidate="x", composite_score=3.0, score_history=(3.0,), goodhart_warnings=0, force_save=False)
    assert state_no_history.plateau_delta is None

    state_with_history = CycleState(cycle=1, candidate="x", composite_score=3.5, score_history=(3.0, 3.5), goodhart_warnings=0, force_save=False)
    assert abs(state_with_history.plateau_delta - 0.5) < 1e-9


def test_simulation_context_with_config():
    ctx = SimulationContext(domain="gaming", seeds=("a",), run_id="r1", config={"generations": 10})
    ctx2 = ctx.with_config(variants=6)
    assert ctx2.config["generations"] == 10
    assert ctx2.config["variants"] == 6
    assert ctx.config == {"generations": 10}  # original unchanged

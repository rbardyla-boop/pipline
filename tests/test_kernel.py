"""Phase 3 tests: simulation kernel with a null (fake) architecture — no API calls."""

import pytest
from unittest.mock import MagicMock

from uaf.kernel.invariants import (
    InvariantSet,
    InvariantViolation,
    ScoreInRange,
    CandidateNotEmpty,
    ScoreHistoryMonotoneOrPlateau,
    GoodhartWarningsBounded,
)
from uaf.kernel.simulation import SimulationKernel, SimulationResult
from uaf.kernel.state import CycleState, SimulationContext, VerificationResult


# ------------------------------------------------------------------ #
# Null architecture — deterministic, no network, no model load        #
# ------------------------------------------------------------------ #

class _NullCognition:
    architecture_id = "null_v0"
    _counter = 0

    def propose(self, parent, context):
        self._counter += 1
        return f"null_candidate_{self._counter}"

    def embed(self, text):
        # Unique-ish embedding so novelty stays > 0
        h = hash(text) % 1000 / 1000.0
        return [h, 1.0 - h, 0.0]

    def coherence(self, candidate):
        return 0.5

    def reasoning_trace(self):
        return []

    def uncertainty_map(self):
        return {}


class _NullMemory:
    def __init__(self):
        self._archive = []

    def seed(self, items):
        for item in items:
            self._archive.append({"concept": item, "embedding": [0.5, 0.5, 0.0], "novelty": 1.0, "generation": 0})

    def add(self, item, embedding, novelty, generation):
        self._archive.append({"concept": item, "embedding": list(embedding), "novelty": novelty, "generation": generation})

    def novelty_of(self, embedding):
        return 0.9  # always novel

    def retired_ids(self):
        return set()

    def retire(self, item, score, combined, run_id):
        pass

    def session_snapshot(self):
        return {"archive_size": len(self._archive), "session_embeddings": [], "refractory_clusters": []}


class _HaltAfterNPlanner:
    def __init__(self, n):
        self._n = n

    def initial_action(self, ctx):
        return "continue"

    def next_action(self, state):
        return "halt" if self.should_halt(state) else "continue"

    def should_halt(self, state):
        return state.cycle >= self._n - 1


class _NullVerification:
    def __init__(self, score=3.5):
        self._score = score

    def score(self, candidate, ctx):
        return VerificationResult(
            composite_score=self._score,
            criteria_scores={"hook_strength": 4},
            ritual_cost_score=0.0,
            anti_optimization_score=0.0,
            improvement_context="improve hook_strength",
            goodhart_warning=False,
            verdict="SLOP",
            extended_verdict="SLOP",
        )

    def verdict(self, result):
        return result.verdict


class _NullRuntime:
    _run_id = "null-run-001"

    def ingest_context(self, domain):
        return f"[CONTEXT for {domain}]"

    def secure_call(self, fn, *args, **kwargs):
        return fn(*args, **kwargs)

    def persist(self, key, payload):
        pass

    def run_id(self):
        return self._run_id


def _make_kernel(n_cycles=3, score=3.5, invariants=None):
    return SimulationKernel(
        cognition=_NullCognition(),
        memory=_NullMemory(),
        planner=_HaltAfterNPlanner(n_cycles),
        verification=_NullVerification(score=score),
        runtime=_NullRuntime(),
        invariants=invariants or InvariantSet.default(),
    )


def _make_ctx(domain="gaming", seeds=("seed_a", "seed_b"), config=None):
    return SimulationContext(domain=domain, seeds=seeds, run_id="r1", config=config or {})


# ------------------------------------------------------------------ #
# Kernel: basic run                                                   #
# ------------------------------------------------------------------ #


def test_kernel_runs_to_completion():
    kernel = _make_kernel(n_cycles=3)
    result = kernel.run(_make_ctx())
    assert isinstance(result, SimulationResult)
    assert result.total_cycles == 3


def test_kernel_produces_best_candidate():
    kernel = _make_kernel(n_cycles=4, score=4.0)
    result = kernel.run(_make_ctx())
    assert result.best_candidate.startswith("null_candidate_")
    assert result.best_score == 4.0


def test_kernel_cycle_records_length():
    kernel = _make_kernel(n_cycles=5)
    result = kernel.run(_make_ctx())
    assert len(result.cycle_records) == 5


def test_kernel_run_id_matches_runtime():
    kernel = _make_kernel()
    result = kernel.run(_make_ctx())
    assert result.run_id == "null-run-001"


def test_kernel_seeds_memory():
    mem = _NullMemory()
    kernel = SimulationKernel(
        cognition=_NullCognition(),
        memory=mem,
        planner=_HaltAfterNPlanner(1),
        verification=_NullVerification(),
        runtime=_NullRuntime(),
    )
    kernel.run(_make_ctx(seeds=("a", "b", "c")))
    # 3 seeds + 1 evolved candidate
    assert len(mem._archive) >= 3


def test_kernel_injects_improvement_context():
    """Improvement context from verification must feed back into zeitgeist."""
    # We verify indirectly: if cognition.propose receives a context containing
    # the improvement directive, the kernel is wiring correctly.
    class _ContextCapture:
        architecture_id = "capture_v0"
        last_context = ""
        _counter = 0

        def propose(self, parent, context):
            self.__class__.last_context = context
            self.__class__._counter += 1
            return f"c_{self._counter}"

        def embed(self, text):
            return [0.5, 0.5, 0.0]

        def coherence(self, c):
            return 0.5

    capture = _ContextCapture()
    kernel = SimulationKernel(
        cognition=capture,
        memory=_NullMemory(),
        planner=_HaltAfterNPlanner(2),
        verification=_NullVerification(),
        runtime=_NullRuntime(),
    )
    kernel.run(_make_ctx())
    # By cycle 2, improvement_context should have been appended
    assert "improve hook_strength" in _ContextCapture.last_context


# ------------------------------------------------------------------ #
# Invariants                                                          #
# ------------------------------------------------------------------ #


def test_score_in_range_passes():
    inv = ScoreInRange()
    state = CycleState(cycle=0, candidate="x", composite_score=3.0, score_history=(3.0,), goodhart_warnings=0, force_save=False)
    inv.check(state)  # must not raise


def test_score_in_range_raises_above_five():
    inv = ScoreInRange()
    state = CycleState(cycle=0, candidate="x", composite_score=5.5, score_history=(5.5,), goodhart_warnings=0, force_save=False)
    with pytest.raises(InvariantViolation, match="score_in_range"):
        inv.check(state)


def test_score_in_range_raises_below_zero():
    inv = ScoreInRange()
    state = CycleState(cycle=0, candidate="x", composite_score=-0.1, score_history=(-0.1,), goodhart_warnings=0, force_save=False)
    with pytest.raises(InvariantViolation):
        inv.check(state)


def test_candidate_not_empty_raises():
    inv = CandidateNotEmpty()
    state = CycleState(cycle=0, candidate="   ", composite_score=3.0, score_history=(3.0,), goodhart_warnings=0, force_save=False)
    with pytest.raises(InvariantViolation, match="candidate_not_empty"):
        inv.check(state)


def test_no_catastrophic_regression_raises():
    inv = ScoreHistoryMonotoneOrPlateau()
    state = CycleState(cycle=1, candidate="x", composite_score=1.0, score_history=(3.5, 1.0), goodhart_warnings=0, force_save=False)
    with pytest.raises(InvariantViolation, match="score_no_catastrophic"):
        inv.check(state)


def test_goodhart_bounded_raises():
    inv = GoodhartWarningsBounded(max_warnings=3)
    state = CycleState(cycle=5, candidate="x", composite_score=3.0, score_history=(3.0,), goodhart_warnings=4, force_save=False)
    with pytest.raises(InvariantViolation, match="goodhart"):
        inv.check(state)


def test_invariant_set_enforce_stops_at_first():
    inv_set = InvariantSet(invariants=[ScoreInRange(), CandidateNotEmpty()])
    bad_state = CycleState(cycle=0, candidate="", composite_score=6.0, score_history=(6.0,), goodhart_warnings=0, force_save=False)
    with pytest.raises(InvariantViolation):
        inv_set.enforce(bad_state)


def test_invariant_set_check_all_collects_all():
    inv_set = InvariantSet(invariants=[ScoreInRange(), CandidateNotEmpty()])
    bad_state = CycleState(cycle=0, candidate="", composite_score=6.0, score_history=(6.0,), goodhart_warnings=0, force_save=False)
    violations = inv_set.check_all(bad_state)
    assert len(violations) == 2


def test_kernel_halts_on_invariant_violation():
    """Kernel should not crash, should exhaust max_recover and return a result."""
    class _BadVerification:
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

    kernel = SimulationKernel(
        cognition=_NullCognition(),
        memory=_NullMemory(),
        planner=_HaltAfterNPlanner(10),
        verification=_BadVerification(),
        runtime=_NullRuntime(),
        max_recover=3,
    )
    result = kernel.run(_make_ctx())
    assert "fail_recover" in result.halt_reason
    assert result.total_cycles == 0  # no successful cycles


def test_invariant_set_default():
    iset = InvariantSet.default()
    assert len(iset.invariants) >= 3

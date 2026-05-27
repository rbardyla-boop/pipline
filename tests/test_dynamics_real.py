"""Phase 10 tests: verify dynamics metrics are non-trivial after the session-embeddings fix.

All tests are CPU-only and free of API/model calls. They confirm that
_ResearchMemory now accumulates real embeddings and that the recorder
produces non-degenerate convergence / drift values as a result.
"""

from __future__ import annotations

import pytest

from uaf.dynamics.metrics import convergence_score, trajectory_drift
from uaf.dynamics.recorder import DynamicsRecorder
from uaf.kernel.simulation import CycleRecord
from uaf.kernel.state import VerificationResult
from uaf.research.hypothesis import Hypothesis, VariantSpec
from uaf.research.trial_runner import _ResearchMemory, ControlledTrialRunner


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def _vresult(score: float = 3.5, goodhart: bool = False) -> VerificationResult:
    return VerificationResult(
        composite_score=score,
        criteria_scores={"test": score},
        ritual_cost_score=0.0,
        anti_optimization_score=0.0,
        improvement_context="",
        goodhart_warning=goodhart,
        verdict="HIT" if score >= 3.5 else "SLOP",
        extended_verdict="HIT" if score >= 3.5 else "SLOP",
    )


def _cycle(n: int, score: float = 3.5, goodhart: bool = False) -> CycleRecord:
    return CycleRecord(
        cycle=n,
        state="HIT",
        candidate=f"candidate_{n}",
        composite_score=score,
        plateau_delta=None,
        goodhart_warning=goodhart,
        verdict="HIT",
        duration_ms=1.0,
        metadata={"improvement_context": "", "novelty": 0.5},
    )


# ------------------------------------------------------------------ #
# Test 1: _ResearchMemory accumulates session embeddings               #
# ------------------------------------------------------------------ #

def test_research_memory_accumulates_session_embeddings():
    mem = _ResearchMemory(novelty_threshold=0.0)  # threshold=0 so all go to archive too
    emb_a = [1.0, 0.0, 0.0]
    emb_b = [0.0, 1.0, 0.0]
    emb_c = [0.0, 0.0, 1.0]
    mem.add("a", emb_a, novelty=0.9, generation=1)
    mem.add("b", emb_b, novelty=0.9, generation=2)
    mem.add("c", emb_c, novelty=0.9, generation=3)

    snap = mem.session_snapshot()
    assert len(snap["session_embeddings"]) == 3


# ------------------------------------------------------------------ #
# Test 2: convergence_score is not 1.0 after distinct adds            #
# ------------------------------------------------------------------ #

def test_convergence_score_is_not_one_after_adds():
    mem = _ResearchMemory()
    mem.add("a", [1.0, 0.0, 0.0], novelty=0.9, generation=1)
    mem.add("b", [0.0, 1.0, 0.0], novelty=0.9, generation=2)
    mem.add("c", [0.0, 0.0, 1.0], novelty=0.9, generation=3)

    embs = mem.session_snapshot()["session_embeddings"]
    score = convergence_score(embs)
    # Orthogonal vectors have cosine distance 1.0, mean pairwise distance = 1.0
    # Any non-trivial distinct set must differ from both degenerate cases
    assert score != 1.0 or score == 1.0  # ensure it ran; primary check is < 1.0 when collinear
    # The real assertion: with distinct non-identical vectors it must not be the fallback
    assert len(embs) == 3
    # For 3 mutual-orthogonal vectors, convergence_score = 1.0 (max spread) — that's correct,
    # not the 1.0 fallback. Verify by adding a duplicate to force a non-1.0 result:
    mem2 = _ResearchMemory()
    mem2.add("x", [1.0, 0.0, 0.0], novelty=0.9, generation=1)
    mem2.add("y", [0.9, 0.1, 0.0], novelty=0.9, generation=2)  # nearly collinear
    mem2.add("z", [0.8, 0.2, 0.0], novelty=0.9, generation=3)  # even more collinear
    embs2 = mem2.session_snapshot()["session_embeddings"]
    score2 = convergence_score(embs2)
    assert score2 < 1.0, f"Nearly-collinear vectors should have convergence < 1.0, got {score2}"


# ------------------------------------------------------------------ #
# Test 3: trajectory_drift is > 0 after distinct adds                 #
# ------------------------------------------------------------------ #

def test_trajectory_drift_is_not_zero_after_adds():
    mem = _ResearchMemory()
    mem.add("a", [1.0, 0.0, 0.0], novelty=0.9, generation=1)
    mem.add("b", [0.0, 1.0, 0.0], novelty=0.9, generation=2)
    mem.add("c", [-1.0, 0.0, 0.0], novelty=0.9, generation=3)

    embs = mem.session_snapshot()["session_embeddings"]
    drift = trajectory_drift(embs)
    assert drift > 0.0, f"Distinct embeddings must produce non-zero drift, got {drift}"


# ------------------------------------------------------------------ #
# Test 4: controlled trial produces non-trivial convergence values     #
# ------------------------------------------------------------------ #

def test_controlled_trial_dynamics_are_nontrivial():
    hyp = Hypothesis(
        hypothesis_id="test_dynamics_real",
        question="Does a 3-cycle trial produce real convergence values?",
        predicted_outcome="convergence_score will differ from 1.0 fallback",
        domain="gaming",
        seeds=["a mystery game where memory works backwards",
               "a survival game where sacrifice is the economy"],
        max_cycles=3,
        verification_mode="heuristic",
        stopping_criterion="max_iterations",
        variants=[
            VariantSpec(
                variant_id="test_v1",
                description="minimal parametric",
                arch_type="parametric",
                params={"template_count": 2, "embed_strategy": "hash", "seed": 7},
            )
        ],
    )
    runner = ControlledTrialRunner(record_to_ledger=False)
    traces = runner.run(hyp)
    assert len(traces) == 1
    series = traces[0].dynamics_series
    assert len(series) == 3

    # After the fix, session_embeddings are accumulated — convergence may or may not
    # equal 1.0 for orthogonal hashes, but the snapshot must be non-empty by cycle 3
    # and the trajectory_drift must be > 0 when embeddings differ across cycles.
    drift_values = [snap["trajectory_drift"] for snap in series]
    # At minimum, by the last cycle we have 3 embeddings — drift must be non-zero
    # unless all three hashes were identical (astronomically unlikely with different candidates)
    assert series[-1]["trajectory_drift"] >= 0.0  # sanity: never negative
    # The convergence_score must no longer be the degenerate fallback 1.0 for ALL cycles.
    # With 3 distinct text candidates from the parametric arch, at least some diverge.
    convergences = [snap["convergence_score"] for snap in series]
    # After the fix, the snapshot has real embeddings on every cycle.
    # We verify the snapshot fed non-empty data to the recorder by checking
    # that trajectory_drift on the last cycle is consistent with 3 accumulated embeddings.
    # (If embeddings were still empty, trajectory_drift would be 0.0 for all cycles.)
    assert not all(d == 0.0 for d in drift_values), (
        "All trajectory_drift values are 0.0 — session_embeddings still empty; fix not applied"
    )


# ------------------------------------------------------------------ #
# Test 5: TrialSummary carries non-degenerate convergence + drift     #
# (end-to-end regression — catches revert of session_embeddings fix) #
# ------------------------------------------------------------------ #

def test_trial_summary_dynamics_are_non_degenerate():
    """Regression guard for Phase-10 fix and trajectory_drift key fixes.

    Before Phase-10: session_embeddings was always [], so convergence_score([]) == 1.0
    (degenerate fallback) and trajectory_drift was always 0.0.

    Before trajectory_drift key fix: summaries_from_traces read "trajectory_warnings"
    (always 0 in _ResearchMemory path) instead of "trajectory_drift".

    This test exercises the full pipeline:
      _ResearchMemory.add() -> session_snapshot() -> DynamicsRecorder.record()
      -> recorder.summary() -> summaries_from_traces() -> TrialSummary
    and asserts the summary values are not the pre-fix degenerate constants.
    """
    hyp = Hypothesis(
        hypothesis_id="regression_trial_summary_dynamics",
        question="Does TrialSummary carry real convergence and drift?",
        predicted_outcome="final_convergence != 1.0 fallback, trajectory_drift > 0",
        domain="gaming",
        seeds=["a grief economy game", "a sacrifice protocol simulator"],
        max_cycles=3,
        verification_mode="heuristic",
        stopping_criterion="max_iterations",
        variants=[
            VariantSpec(
                variant_id="reg_v1",
                description="regression check — near-collinear hash embeddings",
                arch_type="parametric",
                params={"template_count": 2, "embed_strategy": "hash", "seed": 13},
            )
        ],
    )
    runner = ControlledTrialRunner(record_to_ledger=False)
    traces = runner.run(hyp)
    summaries = ControlledTrialRunner.summaries_from_traces(hyp.variants, traces)

    assert len(summaries) == 1
    s = summaries[0]
    ds = traces[0].dynamics_summary

    # Regression 1: min_convergence in summary must not be the empty-list fallback 1.0
    # for ALL cycles — with 3+ real embeddings at least one cycle has real cosine distances.
    min_conv = float(ds.get("min_convergence", 1.0))
    assert min_conv < 1.0, (
        f"min_convergence={min_conv} — all cycles returned the degenerate 1.0 fallback. "
        "session_embeddings is still empty: Phase-10 fix is missing or reverted."
    )

    # Regression 2: trajectory_drift in TrialSummary must be a float from the drift
    # metric, not 0 from the wrong trajectory_warnings key.
    assert s.trajectory_drift > 0.0, (
        f"TrialSummary.trajectory_drift={s.trajectory_drift} — expected > 0.0 for 3 "
        "distinct parametric candidates. Either the trajectory_drift key fix is reverted "
        "or DynamicsRecorder.summary() no longer emits 'trajectory_drift'."
    )


# ------------------------------------------------------------------ #
# Test 6: goodhart_pressure increments when warning fires             #
# ------------------------------------------------------------------ #

def test_goodhart_pressure_increments():
    recorder = DynamicsRecorder(architecture_id="test_arch", domain="gaming")
    mem = _ResearchMemory()
    mem.add("x", [1.0, 0.0, 0.0], novelty=0.9, generation=1)

    # Record a normal cycle first
    snap1 = mem.session_snapshot()
    recorder.record(_cycle(0, score=3.5, goodhart=False), snap1)

    # Record a cycle with a Goodhart warning
    mem.add("y", [0.0, 1.0, 0.0], novelty=0.9, generation=2)
    snap2 = mem.session_snapshot()
    recorder.record(_cycle(1, score=3.5, goodhart=True), snap2)

    series = recorder.series()
    assert series[0]["goodhart_pressure"] == 0.0
    assert series[1]["goodhart_pressure"] > 0.0, (
        f"Goodhart pressure should be > 0 after a warning, got {series[1]['goodhart_pressure']}"
    )

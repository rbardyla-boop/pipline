"""Phase 4 tests: Systems Dynamics Layer — pure metric functions and recorder.

All tests use known vectors with analytically computable expected values.
No randomness, no mocking, no network calls.
"""

import math
import pytest

from uaf.dynamics.metrics import (
    convergence_score,
    cosine_distance,
    cosine_similarity,
    goodhart_pressure,
    novelty_pressure,
    plateau_distance,
    refractory_load,
    stability,
    trajectory_drift,
)
from uaf.dynamics.trajectory import (
    session_converging,
    trajectory_summary,
    volatile_weights,
    weighted_path_length,
)
from uaf.dynamics.recorder import DynamicsRecorder, DynamicsSnapshot
from uaf.kernel.simulation import CycleRecord


# ------------------------------------------------------------------ #
# Known vectors                                                       #
# ------------------------------------------------------------------ #

_ORTHO_A = [1.0, 0.0, 0.0]
_ORTHO_B = [0.0, 1.0, 0.0]
_SAME    = [1.0, 0.0, 0.0]
_ANTIP   = [-1.0, 0.0, 0.0]


# ------------------------------------------------------------------ #
# cosine_similarity / cosine_distance                                 #
# ------------------------------------------------------------------ #


def test_cosine_similarity_identical():
    assert abs(cosine_similarity(_SAME, _SAME) - 1.0) < 1e-9


def test_cosine_similarity_orthogonal():
    assert abs(cosine_similarity(_ORTHO_A, _ORTHO_B)) < 1e-9


def test_cosine_similarity_antipodal():
    assert abs(cosine_similarity(_SAME, _ANTIP) - (-1.0)) < 1e-9


def test_cosine_distance_zero_for_identical():
    assert abs(cosine_distance(_SAME, _SAME)) < 1e-9


def test_cosine_distance_one_for_orthogonal():
    assert abs(cosine_distance(_ORTHO_A, _ORTHO_B) - 1.0) < 1e-9


def test_cosine_distance_two_for_antipodal():
    assert abs(cosine_distance(_SAME, _ANTIP) - 2.0) < 1e-9


def test_cosine_similarity_zero_vector():
    assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0


# ------------------------------------------------------------------ #
# convergence_score                                                   #
# ------------------------------------------------------------------ #


def test_convergence_empty():
    assert convergence_score([]) == 1.0


def test_convergence_one_item():
    assert convergence_score([[1.0, 0.0]]) == 1.0


def test_convergence_identical_pair():
    # Two identical vectors → distance = 0 → convergence = 0
    assert abs(convergence_score([[1.0, 0.0], [1.0, 0.0]])) < 1e-9


def test_convergence_orthogonal_pair():
    # Two orthogonal vectors → distance = 1.0 → convergence = 1.0
    assert abs(convergence_score([_ORTHO_A, _ORTHO_B]) - 1.0) < 1e-9


def test_convergence_three_orthogonal():
    e1, e2, e3 = [1, 0, 0], [0, 1, 0], [0, 0, 1]
    # All pairs orthogonal → mean distance = 1.0
    assert abs(convergence_score([e1, e2, e3]) - 1.0) < 1e-9


# ------------------------------------------------------------------ #
# trajectory_drift                                                    #
# ------------------------------------------------------------------ #


def test_drift_empty():
    assert trajectory_drift([]) == 0.0


def test_drift_single():
    assert trajectory_drift([[1.0, 0.0]]) == 0.0


def test_drift_two_orthogonal():
    # One step from [1,0] to [0,1] = cosine distance 1.0
    assert abs(trajectory_drift([_ORTHO_A, _ORTHO_B]) - 1.0) < 1e-9


def test_drift_three_steps():
    # [1,0] → [0,1] → [-1,0]: two steps each distance 1.0 → total 2.0
    steps = [[1.0, 0.0], [0.0, 1.0], [-1.0, 0.0]]
    assert abs(trajectory_drift(steps) - 2.0) < 1e-9


# ------------------------------------------------------------------ #
# stability                                                           #
# ------------------------------------------------------------------ #


def test_stability_empty():
    assert stability([]) == 0.0


def test_stability_single():
    assert stability([3.5]) == 0.0


def test_stability_constant():
    assert stability([3.0, 3.0, 3.0]) == 0.0


def test_stability_known_variance():
    # [2, 4] → mean=3, variance = (1+1)/2 = 1.0
    assert abs(stability([2.0, 4.0]) - 1.0) < 1e-9


# ------------------------------------------------------------------ #
# plateau_distance                                                    #
# ------------------------------------------------------------------ #


def test_plateau_none_on_single():
    assert plateau_distance([3.5]) is None


def test_plateau_correct_abs_delta():
    assert abs(plateau_distance([3.0, 3.8]) - 0.8) < 1e-9


def test_plateau_regression():
    # regression is also captured as absolute distance
    assert abs(plateau_distance([4.0, 3.5]) - 0.5) < 1e-9


# ------------------------------------------------------------------ #
# goodhart_pressure                                                   #
# ------------------------------------------------------------------ #


def test_goodhart_zero_cycles():
    assert goodhart_pressure(3, 0) == 0.0


def test_goodhart_rate():
    assert abs(goodhart_pressure(2, 4) - 0.5) < 1e-9


# ------------------------------------------------------------------ #
# novelty_pressure                                                    #
# ------------------------------------------------------------------ #


def test_novelty_pressure_empty():
    result = novelty_pressure([])
    assert result == {"mean": 0.0, "std": 0.0, "min": 0.0, "max": 0.0}


def test_novelty_pressure_known():
    result = novelty_pressure([0.8, 0.9, 0.7])
    assert abs(result["mean"] - 0.8) < 1e-4
    assert result["min"] == 0.7
    assert result["max"] == 0.9


# ------------------------------------------------------------------ #
# refractory_load                                                     #
# ------------------------------------------------------------------ #


def test_refractory_load_empty():
    assert refractory_load([], current_cycle=5) == 0.0


def test_refractory_load_all_active():
    clusters = [{"cycle_added": 4}, {"cycle_added": 4}]
    assert abs(refractory_load(clusters, current_cycle=5, refractory_cycles=2) - 1.0) < 1e-9


def test_refractory_load_none_active():
    clusters = [{"cycle_added": 0}, {"cycle_added": 1}]
    assert abs(refractory_load(clusters, current_cycle=10, refractory_cycles=2)) < 1e-9


# ------------------------------------------------------------------ #
# trajectory module                                                   #
# ------------------------------------------------------------------ #


def test_session_converging_false_when_spread():
    # Orthogonal vectors → mean distance = 1.0 > threshold
    embs = [[1.0, 0.0], [0.0, 1.0], [-1.0, 0.0]]
    assert session_converging(embs, threshold=0.35) is False


def test_session_converging_true_when_identical():
    # Three identical vectors → mean distance = 0 < threshold
    embs = [[1.0, 0.0, 0.0]] * 3
    assert session_converging(embs, threshold=0.35) is True


def test_session_converging_requires_three():
    assert session_converging([[1.0, 0.0], [0.0, 1.0]], threshold=0.35) is False


def test_volatile_weights_decay():
    w = volatile_weights(n_cycles=3, current_cycle=3, decay_rate=0.05)
    assert len(w) == 3
    # w[0] is oldest: age = 3 - 0 = 3, weight = max(0.1, 1 - 3*0.05) = 0.85
    assert abs(w[0] - 0.85) < 1e-4
    # w[2] is newest: age = 3 - 2 = 1, weight = 0.95
    assert abs(w[2] - 0.95) < 1e-4


def test_trajectory_summary_structure():
    embs = [[1.0, 0.0], [0.0, 1.0], [1.0, 0.0]]
    summary = trajectory_summary(embs, current_cycle=3)
    required_keys = {
        "convergence_score", "trajectory_drift", "weighted_drift",
        "session_converging", "trajectory_warnings", "active_refractory",
    }
    assert required_keys.issubset(summary.keys())


# ------------------------------------------------------------------ #
# DynamicsRecorder                                                    #
# ------------------------------------------------------------------ #


def _make_cycle_record(cycle, score, goodhart=False, plateau=None):
    return CycleRecord(
        cycle=cycle,
        state="SLOP",
        candidate=f"candidate_{cycle}",
        composite_score=score,
        plateau_delta=plateau,
        goodhart_warning=goodhart,
        verdict="SLOP",
        duration_ms=10.0,
    )


def _make_session_snapshot(embs=None):
    return {
        "archive_size": 5,
        "session_embeddings": embs or [],
        "refractory_clusters": [],
        "trajectory_warnings": 0,
        "current_cycle": 0,
    }


def test_recorder_records_cycle():
    rec = DynamicsRecorder(architecture_id="null_v0", domain="gaming")
    cr = _make_cycle_record(0, 3.5)
    snap = rec.record(cr, _make_session_snapshot())
    assert isinstance(snap, DynamicsSnapshot)
    assert snap.composite_score == 3.5
    assert snap.architecture_id == "null_v0"
    assert snap.domain == "gaming"


def test_recorder_series_length():
    rec = DynamicsRecorder(architecture_id="null_v0", domain="gaming")
    for i in range(5):
        rec.record(_make_cycle_record(i, 3.0 + i * 0.1), _make_session_snapshot())
    assert len(rec.series()) == 5


def test_recorder_summary_keys():
    rec = DynamicsRecorder(architecture_id="null_v0", domain="gaming")
    for i in range(3):
        rec.record(_make_cycle_record(i, 3.5), _make_session_snapshot())
    summary = rec.summary()
    assert "final_score" in summary
    assert "best_score" in summary
    assert "mean_score" in summary
    assert "goodhart_total" in summary


def test_recorder_goodhart_count():
    rec = DynamicsRecorder(architecture_id="null_v0", domain="gaming")
    rec.record(_make_cycle_record(0, 3.5, goodhart=True), _make_session_snapshot())
    rec.record(_make_cycle_record(1, 3.5, goodhart=False), _make_session_snapshot())
    rec.record(_make_cycle_record(2, 3.5, goodhart=True), _make_session_snapshot())
    summary = rec.summary()
    assert summary["goodhart_total"] == 2


def test_recorder_empty_summary():
    rec = DynamicsRecorder(architecture_id="null_v0", domain="gaming")
    assert rec.summary() == {}


def test_snapshot_to_dict_is_serialisable():
    rec = DynamicsRecorder(architecture_id="null_v0", domain="gaming")
    snap = rec.record(_make_cycle_record(0, 3.5), _make_session_snapshot())
    d = snap.to_dict()
    assert isinstance(d, dict)
    assert d["composite_score"] == 3.5


def test_recorder_convergence_with_embeddings():
    """With orthogonal session embeddings, convergence_score should be ~1.0."""
    embs_raw = [
        {"emb_list": [1.0, 0.0, 0.0], "cycle": 0, "preview": "x"},
        {"emb_list": [0.0, 1.0, 0.0], "cycle": 1, "preview": "y"},
        {"emb_list": [0.0, 0.0, 1.0], "cycle": 2, "preview": "z"},
    ]
    snap_data = {"archive_size": 3, "session_embeddings": embs_raw,
                 "refractory_clusters": [], "trajectory_warnings": 0, "current_cycle": 2}
    rec = DynamicsRecorder(architecture_id="null_v0", domain="gaming")
    snap = rec.record(_make_cycle_record(2, 3.8), snap_data)
    assert abs(snap.convergence_score - 1.0) < 1e-6

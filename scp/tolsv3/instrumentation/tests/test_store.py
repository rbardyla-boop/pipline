"""
Tests for instrumentation.trace_store and instrumentation.replay.
"""

import math
import tempfile
from pathlib import Path

import pytest

from instrumentation.trace_store import (
    ExperimentRecord,
    capture_git_hash,
    dict_to_report,
    load_record,
    report_to_dict,
    run_and_record,
    save_record,
)
from instrumentation.replay import verify_replay, verify_replay_diff


_PARAMS = dict(n_agents=10, total_mass=100.0, kT_global=0.5, gamma=0.1,
               entropy_budget=20.0, seed=0, ness_window=10, x_range=0.3)


# ---------------------------------------------------------------------------
# Test 1: save/load round-trip preserves all fields including inf
# ---------------------------------------------------------------------------

def test_save_load_roundtrip_with_inf():
    """save_record + load_record must round-trip ExperimentRecord faithfully,
    including float('inf') in autocorrelation_decay_time."""
    rec = run_and_record(_PARAMS, n_steps=50, concept_force=0.5)

    # Force an inf into the report to exercise the sentinel path
    report_dict = dict(rec.report)
    report_dict["autocorrelation_decay_time"] = "Infinity"
    rec_inf = ExperimentRecord(
        record_id=rec.record_id,
        created_utc=rec.created_utc,
        git_hash=rec.git_hash,
        sandbox_params=rec.sandbox_params,
        sim_params=rec.sim_params,
        report=report_dict,
        series=rec.series,
    )

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "test_rec.json"
        save_record(rec_inf, path)
        loaded = load_record(path)

    assert loaded.record_id == rec_inf.record_id
    assert loaded.sandbox_params == rec_inf.sandbox_params
    assert loaded.sim_params == rec_inf.sim_params
    assert loaded.schema_version == rec_inf.schema_version
    assert loaded.report["autocorrelation_decay_time"] == "Infinity"

    # Verify dict_to_report correctly reconstructs inf
    restored = dict_to_report(loaded.report)
    assert math.isinf(restored.autocorrelation_decay_time)
    assert restored.autocorrelation_decay_time > 0


# ---------------------------------------------------------------------------
# Test 2: capture_git_hash returns None in a non-git directory
# ---------------------------------------------------------------------------

def test_capture_git_hash_none_outside_repo():
    with tempfile.TemporaryDirectory() as tmp:
        result = capture_git_hash(cwd=tmp)
    assert result is None


# ---------------------------------------------------------------------------
# Test 3: same seed twice → identical report dict
# ---------------------------------------------------------------------------

def test_same_seed_identical_report():
    rec1 = run_and_record(_PARAMS, n_steps=80, concept_force=0.3)
    rec2 = run_and_record(_PARAMS, n_steps=80, concept_force=0.3)

    # record_id and created_utc are unique per call; everything else must match
    assert rec1.sandbox_params == rec2.sandbox_params
    assert rec1.sim_params == rec2.sim_params
    assert rec1.report == rec2.report


# ---------------------------------------------------------------------------
# Test 4: dict_to_report raises on unknown PhaseState name
# ---------------------------------------------------------------------------

def test_dict_to_report_raises_on_unknown_phase():
    bad_report = {
        "phase_state": "NONEXISTENT_PHASE",
        "survivability": 0.5,
        "entropy_production_rate": 1.0,
        "synchronization_pressure": 0.1,
        "coordination_cost": 0.9,
        "autocorrelation_decay_time": 10.0,
        "autocorr_drift": -0.05,
        "mass_variance_final": 0.01,
        "env_mass_fraction": 0.2,
    }
    with pytest.raises(ValueError, match="Unknown PhaseState"):
        dict_to_report(bad_report)


# ---------------------------------------------------------------------------
# Bonus: run_and_record raises when seed is None
# ---------------------------------------------------------------------------

def test_run_and_record_requires_seed():
    params_no_seed = dict(_PARAMS)
    params_no_seed["seed"] = None
    with pytest.raises(ValueError, match="seed"):
        run_and_record(params_no_seed, n_steps=10)


# ---------------------------------------------------------------------------
# Bonus: replay is bit-exact with atol=0
# ---------------------------------------------------------------------------

def test_verify_replay_exact():
    rec = run_and_record(_PARAMS, n_steps=60, concept_force=0.4)
    assert verify_replay(rec, atol=0.0) is True
    assert verify_replay_diff(rec) == {}

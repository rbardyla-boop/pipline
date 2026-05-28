"""
replay — Deterministic replay and verification of ExperimentRecord runs.

Because NonEquilibriumSandbox uses default_rng(seed) and numpy's IEEE 754
arithmetic, records with a fixed seed replay bit-for-bit on the same machine
and numpy version.  atol=0.0 (exact) is therefore the correct default.
"""

from __future__ import annotations

import math

from entropy_lab import NonEquilibriumSandbox
from entropy_lab.phase_transitions import SurvivabilityReport

from .trace_store import ExperimentRecord, dict_to_report, report_to_dict


def replay(rec: ExperimentRecord) -> SurvivabilityReport:
    """Re-run the simulation described by rec and return a fresh report."""
    sb = NonEquilibriumSandbox(**rec.sandbox_params)
    return sb.simulate(**rec.sim_params)


def verify_replay(rec: ExperimentRecord, *, atol: float = 0.0) -> bool:
    """Return True if replaying rec produces a report within atol of the stored one."""
    diff = verify_replay_diff(rec)
    if not diff:
        return True
    if atol == 0.0:
        return False
    for key, (orig, repl) in diff.items():
        if key == "phase_state":
            return False
        try:
            if abs(float(orig) - float(repl)) > atol:
                return False
        except (TypeError, ValueError):
            return False
    return True


def verify_replay_diff(rec: ExperimentRecord) -> dict[str, tuple]:
    """Return a dict of fields where stored and replayed reports differ.

    Keys map to (stored_value, replayed_value).  Empty dict means exact match.
    """
    replayed = replay(rec)
    original = dict_to_report(rec.report)

    diff: dict[str, tuple] = {}

    if replayed.phase_state != original.phase_state:
        diff["phase_state"] = (original.phase_state.name, replayed.phase_state.name)

    numeric_fields = (
        "survivability",
        "entropy_production_rate",
        "synchronization_pressure",
        "coordination_cost",
        "autocorrelation_decay_time",
        "autocorr_drift",
        "mass_variance_final",
        "env_mass_fraction",
    )
    for field in numeric_fields:
        v_orig = getattr(original, field)
        v_repl = getattr(replayed, field)
        if math.isnan(v_orig) and math.isnan(v_repl):
            continue
        if v_orig != v_repl:
            diff[field] = (v_orig, v_repl)

    return diff

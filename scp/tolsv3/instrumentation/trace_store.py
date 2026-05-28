"""
trace_store — Serialisable record of a single simulation run.

Design decisions:
  - float('inf') serialises as the string sentinel "Infinity" (bare Infinity is
    not valid JSON per RFC 8259; the sentinel round-trips cleanly).
  - seed is mandatory in run_and_record — a record without a seed cannot be
    replayed.
  - save_record writes to a tmp file then os.replace() for atomicity.
"""

from __future__ import annotations

import json
import os
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from entropy_lab import NonEquilibriumSandbox
from entropy_lab.phase_transitions import PhaseState, SurvivabilityReport


_SCHEMA_VERSION: int = 1
_INF_POS = "Infinity"
_INF_NEG = "-Infinity"
_NAN_STR = "NaN"


# ---------------------------------------------------------------------------
# ExperimentRecord
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ExperimentRecord:
    record_id: str
    created_utc: str
    git_hash: str | None
    sandbox_params: dict
    sim_params: dict
    report: dict
    series: dict
    schema_version: int = _SCHEMA_VERSION


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def capture_git_hash(cwd: str | Path | None = None) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None


def _encode_float(v: float) -> Any:
    if v != v:          # NaN
        return _NAN_STR
    if v == float("inf"):
        return _INF_POS
    if v == float("-inf"):
        return _INF_NEG
    return v


def _decode_float(v: Any) -> float:
    if v == _INF_POS:
        return float("inf")
    if v == _INF_NEG:
        return float("-inf")
    if v == _NAN_STR:
        return float("nan")
    return float(v)


# ---------------------------------------------------------------------------
# Report serialisation
# ---------------------------------------------------------------------------

def report_to_dict(report: SurvivabilityReport) -> dict:
    return {
        "phase_state": report.phase_state.name,
        "survivability": _encode_float(report.survivability),
        "entropy_production_rate": _encode_float(report.entropy_production_rate),
        "synchronization_pressure": _encode_float(report.synchronization_pressure),
        "coordination_cost": _encode_float(report.coordination_cost),
        "autocorrelation_decay_time": _encode_float(report.autocorrelation_decay_time),
        "autocorr_drift": _encode_float(report.autocorr_drift),
        "mass_variance_final": _encode_float(report.mass_variance_final),
        "env_mass_fraction": _encode_float(report.env_mass_fraction),
    }


def dict_to_report(d: dict) -> SurvivabilityReport:
    try:
        phase = PhaseState[d["phase_state"]]
    except KeyError:
        raise ValueError(f"Unknown PhaseState name: {d['phase_state']!r}")
    return SurvivabilityReport(
        phase_state=phase,
        survivability=_decode_float(d["survivability"]),
        entropy_production_rate=_decode_float(d["entropy_production_rate"]),
        synchronization_pressure=_decode_float(d["synchronization_pressure"]),
        coordination_cost=_decode_float(d["coordination_cost"]),
        autocorrelation_decay_time=_decode_float(d["autocorrelation_decay_time"]),
        autocorr_drift=_decode_float(d["autocorr_drift"]),
        mass_variance_final=_decode_float(d["mass_variance_final"]),
        env_mass_fraction=_decode_float(d["env_mass_fraction"]),
    )


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_record(rec: ExperimentRecord, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "record_id": rec.record_id,
        "created_utc": rec.created_utc,
        "git_hash": rec.git_hash,
        "sandbox_params": rec.sandbox_params,
        "sim_params": rec.sim_params,
        "report": rec.report,
        "series": rec.series,
        "schema_version": rec.schema_version,
    }
    tmp = path.with_suffix(".tmp")
    try:
        with open(tmp, "w") as f:
            json.dump(payload, f, indent=2)
        os.replace(tmp, path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def load_record(path: Path) -> ExperimentRecord:
    with open(path) as f:
        d = json.load(f)
    if d.get("schema_version") != _SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported schema_version {d.get('schema_version')!r}; "
            f"expected {_SCHEMA_VERSION}"
        )
    return ExperimentRecord(
        record_id=d["record_id"],
        created_utc=d["created_utc"],
        git_hash=d.get("git_hash"),
        sandbox_params=d["sandbox_params"],
        sim_params=d["sim_params"],
        report=d["report"],
        series=d.get("series", {}),
        schema_version=d["schema_version"],
    )


# ---------------------------------------------------------------------------
# run_and_record
# ---------------------------------------------------------------------------

def run_and_record(
    sandbox_params: dict,
    n_steps: int,
    concept_force: float = 0.5,
    *,
    out_dir: Path | None = None,
) -> ExperimentRecord:
    """Run one simulation and package the result as a serialisable record.

    seed is mandatory: a record without a fixed seed cannot be replayed.
    """
    if sandbox_params.get("seed") is None:
        raise ValueError(
            "sandbox_params['seed'] must be an integer, not None. "
            "Records without a seed cannot be replayed."
        )

    sb = NonEquilibriumSandbox(**sandbox_params)
    report = sb.simulate(n_steps=n_steps, concept_force=concept_force)

    rec = ExperimentRecord(
        record_id=uuid.uuid4().hex,
        created_utc=datetime.now(timezone.utc).isoformat(),
        git_hash=capture_git_hash(),
        sandbox_params=dict(sandbox_params),
        sim_params={"n_steps": n_steps, "concept_force": concept_force},
        report=report_to_dict(report),
        series={},
    )

    if out_dir is not None:
        save_record(rec, Path(out_dir) / f"{rec.record_id}.json")

    return rec

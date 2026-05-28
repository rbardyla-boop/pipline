"""
instrumentation — Experiment governance for the entropy_lab.

Provides reproducibility, record/replay, and persistence primitives.
"""

from .trace_store import (
    ExperimentRecord,
    capture_git_hash,
    dict_to_report,
    load_record,
    report_to_dict,
    run_and_record,
    save_record,
)
from .replay import replay, verify_replay, verify_replay_diff

__all__ = [
    "ExperimentRecord",
    "capture_git_hash",
    "dict_to_report",
    "load_record",
    "report_to_dict",
    "run_and_record",
    "save_record",
    "replay",
    "verify_replay",
    "verify_replay_diff",
]

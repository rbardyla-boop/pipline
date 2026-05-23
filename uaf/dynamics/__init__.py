"""UAF Systems Dynamics Layer — metrics, trajectory analysis, and per-cycle recording."""

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
from uaf.dynamics.recorder import DynamicsRecorder, DynamicsSnapshot
from uaf.dynamics.trajectory import (
    session_converging,
    trajectory_summary,
    volatile_weights,
    weighted_path_length,
)

__all__ = [
    "convergence_score",
    "cosine_distance",
    "cosine_similarity",
    "goodhart_pressure",
    "novelty_pressure",
    "plateau_distance",
    "refractory_load",
    "stability",
    "trajectory_drift",
    "DynamicsRecorder",
    "DynamicsSnapshot",
    "session_converging",
    "trajectory_summary",
    "volatile_weights",
    "weighted_path_length",
]

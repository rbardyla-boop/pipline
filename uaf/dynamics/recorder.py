"""DynamicsRecorder — per-cycle snapshot hook for the Systems Dynamics Layer.

The recorder is attached to a SimulationKernel run (or called directly by
experiment runners) to produce a time-series of dynamics observations.
It consumes:
  - CycleRecord from the kernel
  - MemorySystem.session_snapshot()
  - The metric functions from uaf.dynamics.metrics and uaf.dynamics.trajectory

The output is a serialisable list of DynamicsSnapshot dicts, one per cycle,
suitable for experiment ledger storage and cross-architecture comparison.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Sequence

from uaf.dynamics.metrics import (
    convergence_score as _convergence_score,
    goodhart_pressure,
    novelty_pressure,
    plateau_distance,
    refractory_load,
    stability,
    trajectory_drift as _trajectory_drift,
)
from uaf.dynamics.trajectory import session_converging, trajectory_summary, weighted_path_length
from uaf.kernel.simulation import CycleRecord


@dataclass
class DynamicsSnapshot:
    """All dynamics observations for a single simulation cycle."""

    cycle: int
    composite_score: float
    plateau_delta: float | None
    stability: float
    goodhart_pressure: float
    convergence_score: float
    trajectory_drift: float
    weighted_drift: float
    session_converging: bool
    novelty_mean: float
    novelty_std: float
    active_refractory: int
    trajectory_warnings: int
    architecture_id: str
    domain: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


class DynamicsRecorder:
    """Collects per-cycle dynamics snapshots for a simulation run.

    Usage:
        recorder = DynamicsRecorder(architecture_id="claude_novelty_v1", domain="gaming")
        for cycle_record in result.cycle_records:
            snapshot = recorder.record(cycle_record, memory.session_snapshot())
        series = recorder.series()
    """

    def __init__(self, architecture_id: str, domain: str) -> None:
        self._architecture_id = architecture_id
        self._domain = domain
        self._snapshots: list[DynamicsSnapshot] = []
        self._score_history: list[float] = []
        self._goodhart_count: int = 0

    def record(
        self,
        cycle_record: CycleRecord,
        session_snapshot: dict,
        novelty_scores: Sequence[float] | None = None,
    ) -> DynamicsSnapshot:
        """Record a single cycle and return its DynamicsSnapshot.

        Args:
            cycle_record:     CycleRecord from the simulation kernel.
            session_snapshot: Output of MemorySystem.session_snapshot().
            novelty_scores:   Optional per-generation novelty distribution
                              (from archive, if available).
        """
        self._score_history.append(cycle_record.composite_score)
        if cycle_record.goodhart_warning:
            self._goodhart_count += 1

        # Extract embeddings from session snapshot
        raw_embs: list[list] = session_snapshot.get("session_embeddings", [])
        embs: list[list] = [
            e["emb_list"] if isinstance(e, dict) and "emb_list" in e else e
            for e in raw_embs
        ]
        refractory_clusters = session_snapshot.get("refractory_clusters", [])
        current_cycle = cycle_record.cycle
        trajectory_warnings = session_snapshot.get("trajectory_warnings", 0)

        # Compute all metrics
        traj = trajectory_summary(
            embs,
            current_cycle,
            refractory_clusters=refractory_clusters,
            trajectory_warnings=trajectory_warnings,
        )

        np_stats = novelty_pressure(list(novelty_scores) if novelty_scores else [])

        snap = DynamicsSnapshot(
            cycle=current_cycle,
            composite_score=cycle_record.composite_score,
            plateau_delta=cycle_record.plateau_delta,
            stability=round(stability(self._score_history), 6),
            goodhart_pressure=round(goodhart_pressure(self._goodhart_count, current_cycle + 1), 6),
            convergence_score=traj["convergence_score"],
            trajectory_drift=traj["trajectory_drift"],
            weighted_drift=traj["weighted_drift"],
            session_converging=traj["session_converging"],
            novelty_mean=np_stats["mean"],
            novelty_std=np_stats["std"],
            active_refractory=traj["active_refractory"],
            trajectory_warnings=trajectory_warnings,
            architecture_id=self._architecture_id,
            domain=self._domain,
        )
        self._snapshots.append(snap)
        return snap

    def series(self) -> list[dict]:
        """Return all snapshots as a list of serialisable dicts."""
        return [s.to_dict() for s in self._snapshots]

    def summary(self) -> dict:
        """Return aggregate statistics across all recorded cycles."""
        if not self._snapshots:
            return {}
        scores = [s.composite_score for s in self._snapshots]
        convergences = [s.convergence_score for s in self._snapshots]
        return {
            "architecture_id": self._architecture_id,
            "domain": self._domain,
            "total_cycles": len(self._snapshots),
            "final_score": scores[-1],
            "best_score": max(scores),
            "mean_score": round(sum(scores) / len(scores), 4),
            "final_convergence": convergences[-1],
            "min_convergence": min(convergences),
            "goodhart_total": self._goodhart_count,
            "trajectory_warnings": self._snapshots[-1].trajectory_warnings if self._snapshots else 0,
        }

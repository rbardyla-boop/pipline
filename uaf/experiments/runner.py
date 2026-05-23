"""ExperimentRunner — runs an ExperimentDefinition and returns a full trace.

The runner wires together the SimulationKernel and DynamicsRecorder into
a single execute() call that returns an ExperimentTrace — the complete
record for one experiment run, ready for the ledger.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from uaf.dynamics.recorder import DynamicsRecorder
from uaf.experiments.definition import ExperimentDefinition
from uaf.kernel.simulation import SimulationKernel, SimulationResult


@dataclass
class ExperimentTrace:
    """Complete record for one experiment run."""

    experiment_id: str
    architecture_id: str
    run_id: str
    domain: str
    started_at: str
    completed_at: str
    simulation_result: dict[str, Any]
    dynamics_series: list[dict[str, Any]]
    dynamics_summary: dict[str, Any]
    config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "experiment_id": self.experiment_id,
            "architecture_id": self.architecture_id,
            "run_id": self.run_id,
            "domain": self.domain,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "simulation_result": self.simulation_result,
            "dynamics_series": self.dynamics_series,
            "dynamics_summary": self.dynamics_summary,
            "config": self.config,
        }


class ExperimentRunner:
    """Executes an ExperimentDefinition and returns a full ExperimentTrace."""

    def execute(self, defn: ExperimentDefinition) -> ExperimentTrace:
        """Run *defn* to completion and return the full trace."""
        started_at = datetime.now(timezone.utc).isoformat()
        ctx = defn.simulation_context()

        kernel = SimulationKernel(
            cognition=defn.architecture,
            memory=defn.memory,
            planner=defn.planner,
            verification=defn.verification,
            runtime=defn.runtime,
            invariants=defn.invariants,
        )

        result: SimulationResult = kernel.run(ctx)

        # Build dynamics series from cycle records
        recorder = DynamicsRecorder(
            architecture_id=defn.architecture_id(),
            domain=ctx.domain,
        )
        for cycle_record in result.cycle_records:
            session_snap = defn.memory.session_snapshot()
            recorder.record(cycle_record, session_snap)

        completed_at = datetime.now(timezone.utc).isoformat()

        return ExperimentTrace(
            experiment_id=defn.experiment_id,
            architecture_id=defn.architecture_id(),
            run_id=result.run_id,
            domain=result.domain,
            started_at=started_at,
            completed_at=completed_at,
            simulation_result={
                "best_candidate": result.best_candidate,
                "best_score": result.best_score,
                "best_combined": result.best_combined,
                "total_cycles": result.total_cycles,
                "halt_reason": result.halt_reason,
            },
            dynamics_series=recorder.series(),
            dynamics_summary=recorder.summary(),
            config=ctx.config,
        )

"""ExperimentDefinition — the formal binding of a cognition architecture to
all other UAF components for a single reproducible experiment.

An ExperimentDefinition is the unit of comparison in the experiment ledger.
Two runs sharing the same definition (same architecture_id, same config)
are directly comparable across their DynamicsSnapshot series.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from uaf.interfaces.cognition import CognitionEngine
from uaf.interfaces.memory import MemorySystem
from uaf.interfaces.planner import Planner
from uaf.interfaces.runtime import RuntimeEnvironment
from uaf.interfaces.verification import VerificationEngine
from uaf.kernel.invariants import InvariantSet


@dataclass
class ExperimentDefinition:
    """Complete specification for a UAF experiment run.

    Args:
        experiment_id:  Human-readable name (e.g. "creative_evolution_v1").
        architecture:   The CognitionEngine implementation to test.
        memory:         The MemorySystem implementation.
        planner:        The Planner implementation.
        verification:   The VerificationEngine implementation.
        runtime:        The RuntimeEnvironment implementation.
        invariants:     Optional InvariantSet. Defaults to InvariantSet.default().
        config:         Arbitrary key-value configuration (seeds, domain, etc.).
                        Required keys for creative evolution: "domain", "seeds".
    """

    experiment_id: str
    architecture: CognitionEngine
    memory: MemorySystem
    planner: Planner
    verification: VerificationEngine
    runtime: RuntimeEnvironment
    invariants: InvariantSet = field(default_factory=InvariantSet.default)
    config: dict[str, Any] = field(default_factory=dict)

    def architecture_id(self) -> str:
        return self.architecture.architecture_id

    def simulation_context(self) -> "SimulationContext":
        """Build a SimulationContext from this definition's config."""
        from uaf.kernel.state import SimulationContext

        domain = self.config.get("domain", "unknown")
        seeds = tuple(self.config.get("seeds", []))
        run_id = self.runtime.run_id()
        return SimulationContext(
            domain=domain,
            seeds=seeds,
            run_id=run_id,
            config=self.config,
        )

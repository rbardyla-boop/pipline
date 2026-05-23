"""LangGraphPlanner — wraps the orchestrator routing logic as a Planner.

The existing routing logic lives in orchestrator.route_after_refine().
This adapter replicates that logic against the UAF CycleState so the
simulation kernel can call it without importing LangGraph.

The actual LangGraph DAG continues to run unchanged when main.py is used
directly. This adapter is only active when UAF_KERNEL=true.
"""

from __future__ import annotations

import os

from uaf.interfaces.planner import Planner
from uaf.kernel.state import CycleState, SimulationContext

_DEFAULT_MAX_LOOPS = int(os.getenv("MAX_IMPROVEMENT_LOOPS", "4"))
_DEFAULT_PLATEAU_DELTA = float(os.getenv("PLATEAU_DELTA", "0.10"))


class LangGraphPlanner(Planner):
    """Planner that replicates the orchestrator's route_after_refine logic.

    Args:
        max_loops:     Maximum number of improvement cycles before forced halt.
                       Defaults to MAX_IMPROVEMENT_LOOPS env var (4).
        plateau_delta: Minimum score improvement required to continue.
                       Defaults to PLATEAU_DELTA env var (0.10).
    """

    def __init__(
        self,
        max_loops: int = _DEFAULT_MAX_LOOPS,
        plateau_delta: float = _DEFAULT_PLATEAU_DELTA,
    ) -> None:
        self._max_loops = max_loops
        self._plateau_delta = plateau_delta

    # ------------------------------------------------------------------ #
    # Planner                                                             #
    # ------------------------------------------------------------------ #

    def initial_action(self, ctx: SimulationContext) -> str:
        return "continue"

    def next_action(self, state: CycleState) -> str:
        return "halt" if self.should_halt(state) else "continue"

    def should_halt(self, state: CycleState) -> bool:
        """Replicate orchestrator.route_after_refine() halt conditions."""
        if state.force_save:
            return True
        if state.cycle >= self._max_loops:
            return True
        delta = state.plateau_delta
        if delta is not None and abs(delta) < self._plateau_delta:
            return True
        return False

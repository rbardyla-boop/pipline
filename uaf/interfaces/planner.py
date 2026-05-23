"""Planner — the goal-to-action compiler interface.

The planner converts a simulation context and evolving cycle state into
routing decisions. It is the component that decides whether to continue
mutating or to halt and save. Planning is continuous, not one-shot.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from uaf.kernel.state import CycleState, SimulationContext


class Planner(ABC):
    """Continuous goal-to-action router.

    The planner does not generate candidates — that is the cognition
    engine's job. The planner decides what happens *next* based on the
    accumulated cycle history.
    """

    @abstractmethod
    def initial_action(self, ctx: SimulationContext) -> str:
        """Return the first action to take given the simulation context.

        Typically "continue" unless the seeds already satisfy halt criteria.
        """

    @abstractmethod
    def next_action(self, state: CycleState) -> str:
        """Return the next routing decision based on the current cycle state.

        Returns:
            "continue" — run another mutation + verification cycle.
            "halt"     — save results and end the simulation.

        Implementations must call should_halt() internally and return
        "halt" when it returns True.
        """

    @abstractmethod
    def should_halt(self, state: CycleState) -> bool:
        """Return True if the simulation should stop after this cycle.

        Standard halt conditions (from the creative evolution baseline):
          - state.force_save is True
          - state.cycle >= MAX_IMPROVEMENT_LOOPS
          - state.plateau_delta is not None and state.plateau_delta < PLATEAU_DELTA
        Implementations may add or replace these conditions.
        """

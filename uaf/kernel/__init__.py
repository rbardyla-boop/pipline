"""UAF kernel — simulation loop, state types, and runtime invariant engine.

Import SimulationKernel directly from uaf.kernel.simulation to avoid
circular import: simulation.py imports from uaf.interfaces, which imports
from uaf.kernel.state (triggering this __init__ before simulation is ready).
"""

from uaf.kernel.invariants import InvariantSet, InvariantViolation
from uaf.kernel.state import CycleState, SimulationContext, VerificationResult

__all__ = [
    "CycleState",
    "SimulationContext",
    "VerificationResult",
    "InvariantSet",
    "InvariantViolation",
]

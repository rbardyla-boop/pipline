"""Architecture-agnostic simulation kernel.

SimulationKernel drives the core observe→plan→execute→verify→commit loop
over any combination of CognitionEngine, MemorySystem, Planner,
VerificationEngine, and RuntimeEnvironment that satisfies the UAF
interfaces. It does not know about LangGraph, Claude, or any domain logic.

The legacy LangGraph pipeline (orchestrator.py) remains the authoritative
path when UAF_KERNEL is not set. The kernel is activated only when
UAF_KERNEL=true is in the environment (Phase 6 cutover).

Loop state machine:
  INIT → OBSERVE → PLAN → EXECUTE → VERIFY → COMMIT → COMPRESS → STABILIZE
                                           ↘ FAIL_RECOVER (on invariant violation)
                                                        ↘ OBSERVE (retry)
  COMPRESS / STABILIZE → HALT (when planner says "halt")
                       → OBSERVE (next cycle)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from uaf.interfaces.cognition import CognitionEngine
from uaf.interfaces.memory import MemorySystem
from uaf.interfaces.planner import Planner
from uaf.interfaces.runtime import RuntimeEnvironment
from uaf.interfaces.verification import VerificationEngine
from uaf.kernel.invariants import InvariantSet, InvariantViolation
from uaf.kernel.state import CycleState, SimulationContext, VerificationResult


class SimulatorState(Enum):
    INIT = auto()
    OBSERVE = auto()
    PLAN = auto()
    EXECUTE = auto()
    VERIFY = auto()
    COMMIT = auto()
    COMPRESS = auto()
    STABILIZE = auto()
    FAIL_RECOVER = auto()
    HALT = auto()


@dataclass
class CycleRecord:
    """Full trace record for a single simulation cycle."""

    cycle: int
    state: str
    candidate: str
    composite_score: float
    plateau_delta: float | None
    goodhart_warning: bool
    verdict: str
    duration_ms: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SimulationResult:
    """Final result returned after the kernel loop completes."""

    run_id: str
    domain: str
    best_candidate: str
    best_score: float
    best_combined: float
    total_cycles: int
    cycle_records: list[CycleRecord]
    halt_reason: str
    metadata: dict[str, Any] = field(default_factory=dict)


class SimulationKernel:
    """Architecture-agnostic simulation loop.

    Args:
        cognition:    The cognition engine to use for mutation.
        memory:       The memory system for archive + session state.
        planner:      The planner for routing decisions.
        verification: The verification engine for candidate evaluation.
        runtime:      The runtime environment for context ingestion + persistence.
        invariants:   Optional InvariantSet. Defaults to InvariantSet.default().
        max_recover:  Maximum consecutive FAIL_RECOVER cycles before aborting.
    """

    def __init__(
        self,
        cognition: CognitionEngine,
        memory: MemorySystem,
        planner: Planner,
        verification: VerificationEngine,
        runtime: RuntimeEnvironment,
        invariants: InvariantSet | None = None,
        max_recover: int = 3,
    ) -> None:
        self._cognition = cognition
        self._memory = memory
        self._planner = planner
        self._verification = verification
        self._runtime = runtime
        self._invariants = invariants or InvariantSet.default()
        self._max_recover = max_recover

    def run(self, ctx: SimulationContext) -> SimulationResult:
        """Execute the full simulation loop for *ctx* and return results."""
        run_id = self._runtime.run_id()
        cycle_records: list[CycleRecord] = []
        score_history: tuple[float, ...] = ()
        goodhart_warnings = 0
        best_candidate = ""
        best_score = 0.0
        best_combined = 0.0
        consecutive_failures = 0

        # Boot: seed memory, ingest context
        self._memory.seed(list(ctx.seeds))
        zeitgeist = self._runtime.ingest_context(ctx.domain)

        sim_state = SimulatorState.INIT
        action = self._planner.initial_action(ctx)
        cycle = 0
        candidate = list(ctx.seeds)[0] if ctx.seeds else ""

        while sim_state != SimulatorState.HALT:
            t0 = time.perf_counter()
            sim_state = SimulatorState.OBSERVE

            # ---- EXECUTE ----
            sim_state = SimulatorState.EXECUTE
            try:
                candidate = self._cognition.propose(candidate, zeitgeist)
            except Exception as e:
                sim_state = SimulatorState.FAIL_RECOVER
                consecutive_failures += 1
                if consecutive_failures >= self._max_recover:
                    break
                continue

            # ---- VERIFY ----
            sim_state = SimulatorState.VERIFY
            try:
                vresult: VerificationResult = self._verification.score(candidate, ctx)
            except Exception as e:
                sim_state = SimulatorState.FAIL_RECOVER
                consecutive_failures += 1
                if consecutive_failures >= self._max_recover:
                    break
                continue

            composite = vresult.composite_score
            if vresult.goodhart_warning:
                goodhart_warnings += 1

            score_history = score_history + (composite,)

            # ---- COMMIT (invariant gate) ----
            sim_state = SimulatorState.COMMIT
            cycle_state = CycleState(
                cycle=cycle,
                candidate=candidate,
                composite_score=composite,
                score_history=score_history,
                goodhart_warnings=goodhart_warnings,
                force_save=False,
                verification=vresult,
                metadata={},
            )
            try:
                self._invariants.enforce(cycle_state)
            except InvariantViolation as e:
                sim_state = SimulatorState.FAIL_RECOVER
                consecutive_failures += 1
                if consecutive_failures >= self._max_recover:
                    break
                continue

            # All gates passed — reset failure counter and commit
            consecutive_failures = 0

            # Commit to memory
            emb = list(self._cognition.embed(candidate))
            novelty = self._memory.novelty_of(emb)
            combined = novelty * vresult.composite_score / 5.0
            self._memory.add(candidate, emb, novelty, generation=cycle + 1)

            if composite > best_score:
                best_score = composite
                best_candidate = candidate
                best_combined = combined

            # ---- COMPRESS / STABILIZE ----
            sim_state = SimulatorState.COMPRESS

            duration_ms = (time.perf_counter() - t0) * 1000
            cycle_records.append(CycleRecord(
                cycle=cycle,
                state=vresult.verdict,
                candidate=candidate,
                composite_score=composite,
                plateau_delta=cycle_state.plateau_delta,
                goodhart_warning=vresult.goodhart_warning,
                verdict=vresult.verdict,
                duration_ms=round(duration_ms, 1),
                metadata={"improvement_context": vresult.improvement_context, "novelty": novelty},
            ))

            # ---- PLAN (routing decision) ----
            sim_state = SimulatorState.STABILIZE
            action = self._planner.next_action(cycle_state)
            cycle += 1

            if action == "halt":
                sim_state = SimulatorState.HALT
            else:
                # Inject improvement context into next zeitgeist for continuity
                if vresult.improvement_context:
                    zeitgeist = zeitgeist + "\n" + vresult.improvement_context

        # Determine halt reason
        if consecutive_failures >= self._max_recover:
            halt_reason = f"fail_recover_limit ({self._max_recover} consecutive failures)"
        elif cycle_records:
            last = CycleState(
                cycle=cycle_records[-1].cycle,
                candidate=cycle_records[-1].candidate,
                composite_score=cycle_records[-1].composite_score,
                score_history=tuple(r.composite_score for r in cycle_records),
                goodhart_warnings=goodhart_warnings,
                force_save=False,
            )
            if last.force_save:
                halt_reason = "force_save"
            elif last.cycle >= (ctx.config.get("max_loops", 4) - 1):
                halt_reason = "max_loops_reached"
            elif last.plateau_delta is not None and abs(last.plateau_delta) < ctx.config.get("plateau_delta", 0.10):
                halt_reason = "plateau_detected"
            else:
                halt_reason = "planner_halt"
        else:
            halt_reason = "no_cycles_completed"

        return SimulationResult(
            run_id=run_id,
            domain=ctx.domain,
            best_candidate=best_candidate,
            best_score=best_score,
            best_combined=best_combined,
            total_cycles=cycle,
            cycle_records=cycle_records,
            halt_reason=halt_reason,
        )

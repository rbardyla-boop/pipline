"""BackgroundRunner + LoopState — thread-safe bridge between ExperimentLoop and Streamlit.

ExperimentLoop.run() blocks the calling thread. Streamlit renders on the main thread.
This module:
  1. Runs the loop in a background thread.
  2. Pipes IterationResult events through a queue so Streamlit can consume them.
  3. Exposes pause/resume/stop/inject_variant controls via threading.Event objects.
"""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass, field
from typing import Any

from uaf.research.hypothesis import Hypothesis, VariantSpec


# ------------------------------------------------------------------ #
# Data shapes flowing through the queue                              #
# ------------------------------------------------------------------ #


@dataclass
class IterationResult:
    iteration: int
    hypothesis_snapshot: dict                       # hypothesis.to_dict() at time of callback
    summaries: list[dict]                           # TrialSummary dicts
    comparison: dict
    traces_metadata: list[dict]                     # lightweight: arch_id, best_score, halt_reason per trace
    dynamics_series_by_variant: dict[str, list[dict]] = field(default_factory=dict)  # full per-cycle data
    panel_proposals: list[dict] | None = None       # serialized PanelProposals if panel ran


@dataclass
class LoopEvent:
    kind: str                          # "iteration" | "complete" | "error"
    payload: IterationResult | str     # IterationResult or error/completion message


# ------------------------------------------------------------------ #
# LoopState — session state container (serialisable fields only)      #
# ------------------------------------------------------------------ #


@dataclass
class LoopState:
    hypothesis: Hypothesis | None = None
    iteration_results: list[IterationResult] = field(default_factory=list)
    status: str = "idle"               # idle | running | paused | complete | error
    error_message: str = ""
    resolution: str = ""

    def latest_summaries(self) -> list[dict]:
        if not self.iteration_results:
            return []
        return self.iteration_results[-1].summaries

    def summaries_by_iteration(self) -> list[list[dict]]:
        return [r.summaries for r in self.iteration_results]

    def all_trial_records(self) -> list[dict]:
        """Flat list of param+score records for parallel coordinates chart."""
        records = []
        for r in self.iteration_results:
            for s in r.summaries:
                hyp_snap = r.hypothesis_snapshot
                # Find variant spec params from hypothesis snapshot
                variants = {v["variant_id"]: v.get("params", {})
                            for v in hyp_snap.get("variants", [])}
                params = variants.get(s.get("variant_id", ""), {})
                records.append({
                    "variant_id": s.get("variant_id", ""),
                    "iteration": r.iteration,
                    "best_score": s.get("best_score", 0.0),
                    "template_count": params.get("template_count", 4),
                    "context_injection": params.get("context_injection", True),
                    "coherence_mode": params.get("coherence_mode", "slot_ratio"),
                    "embed_strategy": params.get("embed_strategy", "hash"),
                    "seed": params.get("seed", 42),
                })
        return records

    def series_by_variant(self) -> dict[str, list[dict]]:
        """Aggregate per-cycle dynamics snapshots per variant across all iterations.

        Uses real dynamics_series_by_variant data from IterationResult when available.
        Each cycle record is offset so cycles are globally ordered across iterations.
        """
        series: dict[str, list[dict]] = {}
        global_cycle_offset = 0

        for r in self.iteration_results:
            if r.dynamics_series_by_variant:
                # Use real per-cycle data
                for arch_id, snapshots in r.dynamics_series_by_variant.items():
                    if arch_id not in series:
                        series[arch_id] = []
                    for snap in snapshots:
                        entry = dict(snap)
                        entry["cycle"] = global_cycle_offset + snap.get("cycle", 0)
                        series[arch_id].append(entry)
                # Advance offset by the max cycles seen in this iteration
                all_cycles = [
                    snap.get("cycle", 0)
                    for snaps in r.dynamics_series_by_variant.values()
                    for snap in snaps
                ]
                global_cycle_offset += (max(all_cycles) + 1) if all_cycles else 1
            else:
                # Fallback: synthesise one snapshot per iteration from aggregates
                for tm in r.traces_metadata:
                    vid = tm.get("architecture_id", "unknown")
                    if vid not in series:
                        series[vid] = []
                    series[vid].append({
                        "cycle": global_cycle_offset,
                        "composite_score": tm.get("best_score", 0.0),
                        "convergence_score": tm.get("convergence", 0.0),
                        "goodhart_pressure": float(tm.get("goodhart_total", 0)),
                        "trajectory_drift": tm.get("trajectory_drift", 0.0),
                    })
                global_cycle_offset += 1

        return series


# ------------------------------------------------------------------ #
# BackgroundRunner                                                    #
# ------------------------------------------------------------------ #


class BackgroundRunner:
    """Manages a background ExperimentLoop thread with pause/resume/inject support.

    Usage::

        runner = BackgroundRunner()
        runner.start(hypothesis, max_iterations=5)
        while runner.has_events():
            event = runner.next_event()
            # update st.session_state with event.payload
    """

    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._queue: queue.Queue[LoopEvent] = queue.Queue()
        self._pause_event = threading.Event()
        self._pause_event.set()          # not paused initially
        self._stop_event = threading.Event()
        self._inject_queue: queue.Queue[VariantSpec] = queue.Queue()

    # ---------------------------------------------------------------- #
    # Public control API                                                #
    # ---------------------------------------------------------------- #

    def start(
        self,
        hypothesis: Hypothesis,
        max_iterations: int = 5,
        record_to_ledger: bool = False,
        api_client=None,
    ) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._pause_event.set()
        self._thread = threading.Thread(
            target=self._run,
            args=(hypothesis, max_iterations, record_to_ledger, api_client),
            daemon=True,
        )
        self._thread.start()

    def pause(self) -> None:
        self._pause_event.clear()

    def resume(self) -> None:
        self._pause_event.set()

    def stop(self) -> None:
        self._stop_event.set()
        self._pause_event.set()     # unblock if paused

    def inject_variant(self, spec: VariantSpec) -> None:
        self._inject_queue.put(spec)

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def has_events(self) -> bool:
        return not self._queue.empty()

    def drain_events(self) -> list[LoopEvent]:
        events: list[LoopEvent] = []
        while not self._queue.empty():
            try:
                events.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return events

    # ---------------------------------------------------------------- #
    # Internal                                                          #
    # ---------------------------------------------------------------- #

    def _run(
        self,
        hypothesis: Hypothesis,
        max_iterations: int,
        record_to_ledger: bool,
        api_client,
    ) -> None:
        from uaf.research.loop import ExperimentLoop
        from uaf.research.hypothesis import TrialSummary

        def on_iteration(hyp, traces, summaries, comparison):
            # Pause point — blocks here if paused
            self._pause_event.wait()
            if self._stop_event.is_set():
                return

            # Drain any injected variants
            extras: list[VariantSpec] = []
            while not self._inject_queue.empty():
                try:
                    extras.append(self._inject_queue.get_nowait())
                except queue.Empty:
                    break
            if extras:
                hyp.variants = hyp.variants + extras

            # Convert TrialSummary namedtuples to plain dicts
            summaries_dicts = [
                {
                    "variant_id": s.variant_id,
                    "architecture_id": s.architecture_id,
                    "best_score": s.best_score,
                    "mean_score": s.mean_score,
                    "final_convergence": s.final_convergence,
                    "goodhart_total": s.goodhart_total,
                    "halt_reason": s.halt_reason,
                    "total_cycles": s.total_cycles,
                    "best_candidate": s.best_candidate,
                }
                for s in summaries
            ]

            traces_meta = [
                {
                    "architecture_id": t.architecture_id,
                    "best_score": float(t.simulation_result.get("best_score", 0.0)),
                    "halt_reason": t.simulation_result.get("halt_reason", ""),
                    "goodhart_total": t.dynamics_summary.get("goodhart_total", 0),
                    "convergence": float(t.dynamics_summary.get("final_convergence", 0.0)),
                    "trajectory_drift": float(t.dynamics_summary.get("trajectory_warnings", 0)),
                }
                for t in traces
            ]

            # Serialize full per-cycle dynamics for the frontend charts
            dynamics_series_by_variant = {
                t.architecture_id: t.dynamics_series
                for t in traces
                if hasattr(t, "dynamics_series") and t.dynamics_series
            }

            # Serialize panel proposals if the panel ran this iteration
            panel_snap = hyp.to_dict().get("panel_proposals", [])
            panel_proposals_dicts = panel_snap[-1] if panel_snap else None

            result = IterationResult(
                iteration=hyp.iteration,
                hypothesis_snapshot=hyp.to_dict(),
                summaries=summaries_dicts,
                comparison=comparison,
                traces_metadata=traces_meta,
                dynamics_series_by_variant=dynamics_series_by_variant,
                panel_proposals=panel_proposals_dicts,
            )
            self._queue.put(LoopEvent(kind="iteration", payload=result))

        try:
            loop = ExperimentLoop(
                max_iterations=max_iterations,
                record_to_ledger=record_to_ledger,
                client=api_client,
                verbose=False,
                on_iteration=on_iteration,
            )
            final = loop.run(hypothesis)
            self._queue.put(LoopEvent(
                kind="complete",
                payload=f"Loop complete: {final.resolution}",
            ))
        except Exception as exc:
            self._queue.put(LoopEvent(kind="error", payload=str(exc)))

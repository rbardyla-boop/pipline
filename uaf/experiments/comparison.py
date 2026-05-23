"""Cross-architecture comparison utilities.

Takes two or more ExperimentTrace dicts from the ledger and computes
comparative statistics across the key dynamics metrics.
"""

from __future__ import annotations

from typing import Any


def compare_traces(traces: list[dict]) -> dict[str, Any]:
    """Compare multiple experiment traces on key dynamics metrics.

    Args:
        traces: List of ExperimentTrace.to_dict() records, typically from
                the ledger filtered by experiment_id.

    Returns:
        A comparison dict with per-architecture summaries and deltas.
    """
    if not traces:
        return {}
    if len(traces) == 1:
        return {"single_trace": traces[0]["dynamics_summary"]}

    summaries = {}
    for trace in traces:
        arch_id = trace.get("architecture_id", "unknown")
        summaries[arch_id] = trace.get("dynamics_summary", {})

    arch_ids = list(summaries.keys())
    comparison: dict[str, Any] = {"architectures": arch_ids, "summaries": summaries}

    if len(arch_ids) >= 2:
        a, b = arch_ids[0], arch_ids[1]
        sa, sb = summaries[a], summaries[b]
        deltas = {}
        for key in ("final_score", "best_score", "mean_score", "goodhart_total"):
            va = sa.get(key, 0.0)
            vb = sb.get(key, 0.0)
            if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
                deltas[f"{key}_delta ({a} vs {b})"] = round(va - vb, 4)
        comparison["deltas"] = deltas

    return comparison


def best_architecture(traces: list[dict], metric: str = "best_score") -> str | None:
    """Return the architecture_id with the highest value for *metric*.

    Args:
        traces: List of ExperimentTrace dicts.
        metric: Key in dynamics_summary to rank by. Default: "best_score".

    Returns:
        architecture_id string or None if traces is empty.
    """
    if not traces:
        return None
    return max(
        traces,
        key=lambda t: t.get("dynamics_summary", {}).get(metric, 0.0),
    ).get("architecture_id")

"""Pure Plotly figure builders — no Streamlit imports.

All functions accept plain Python data structures and return go.Figure objects
so they can be tested and rendered outside Streamlit if needed.
"""

from __future__ import annotations

from typing import Any

import plotly.graph_objects as go
from plotly.subplots import make_subplots


# ------------------------------------------------------------------ #
# Palette                                                             #
# ------------------------------------------------------------------ #

_VARIANT_COLORS = [
    "#7C3AED",  # violet
    "#2563EB",  # blue
    "#059669",  # emerald
    "#D97706",  # amber
    "#DC2626",  # red
    "#0891B2",  # cyan
    "#7C3AED",  # repeat
    "#DB2777",  # pink
]

_BG = "#0F0F1A"
_SURFACE = "#1A1A2E"
_GRID = "#2D2D4A"
_TEXT = "#E2E8F0"
_SUBTEXT = "#94A3B8"


def _base_layout(**overrides) -> dict:
    return {
        "paper_bgcolor": _BG,
        "plot_bgcolor": _SURFACE,
        "font": {"color": _TEXT, "family": "Inter, system-ui, sans-serif", "size": 12},
        "margin": {"l": 50, "r": 20, "t": 40, "b": 40},
        "legend": {
            "bgcolor": _SURFACE,
            "bordercolor": _GRID,
            "borderwidth": 1,
            "font": {"size": 11},
        },
        **overrides,
    }


# ------------------------------------------------------------------ #
# Score Evolution                                                     #
# ------------------------------------------------------------------ #


def score_evolution(
    summaries_by_iter: list[list[dict]],
) -> go.Figure:
    """Line chart: iteration × best_score per variant.

    Args:
        summaries_by_iter: list of iterations, each a list of dicts with
            keys: variant_id, best_score, mean_score.
    """
    if not summaries_by_iter:
        fig = go.Figure()
        fig.update_layout(**_base_layout(title="Score Evolution"))
        return fig

    # Collect all variant IDs in order of first appearance
    variant_ids: list[str] = []
    seen: set[str] = set()
    for iteration in summaries_by_iter:
        for s in iteration:
            vid = s["variant_id"]
            if vid not in seen:
                variant_ids.append(vid)
                seen.add(vid)

    # Build per-variant series
    fig = go.Figure()
    for i, vid in enumerate(variant_ids):
        color = _VARIANT_COLORS[i % len(_VARIANT_COLORS)]
        best_scores: list[float | None] = []
        mean_scores: list[float | None] = []
        iters: list[int] = []
        for it_idx, iteration in enumerate(summaries_by_iter):
            match = next((s for s in iteration if s["variant_id"] == vid), None)
            if match:
                best_scores.append(match.get("best_score", 0.0))
                mean_scores.append(match.get("mean_score", 0.0))
                iters.append(it_idx + 1)

        fig.add_trace(go.Scatter(
            x=iters,
            y=best_scores,
            mode="lines+markers",
            name=vid,
            line={"color": color, "width": 2},
            marker={"size": 7, "color": color},
            hovertemplate=f"<b>{vid}</b><br>Iteration %{{x}}<br>Best: %{{y:.3f}}<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=iters,
            y=mean_scores,
            mode="lines",
            name=f"{vid} (mean)",
            line={"color": color, "width": 1, "dash": "dot"},
            showlegend=False,
            opacity=0.5,
            hovertemplate=f"<b>{vid} mean</b><br>Iteration %{{x}}<br>Mean: %{{y:.3f}}<extra></extra>",
        ))

    # Target score reference line if present
    fig.update_layout(
        **_base_layout(title="Score Evolution"),
        xaxis={
            "title": "Iteration",
            "tickmode": "linear",
            "tick0": 1,
            "dtick": 1,
            "gridcolor": _GRID,
            "zeroline": False,
        },
        yaxis={
            "title": "Score",
            "range": [0.8, 5.2],
            "gridcolor": _GRID,
            "zeroline": False,
        },
        hovermode="x unified",
    )
    return fig


# ------------------------------------------------------------------ #
# Dynamics Curves                                                     #
# ------------------------------------------------------------------ #


def dynamics_curves(
    series_by_variant: dict[str, list[dict]],
) -> go.Figure:
    """4-subplot: score / convergence / goodhart_pressure / trajectory_drift by cycle.

    Args:
        series_by_variant: variant_id → list of DynamicsSnapshot dicts
            (fields: cycle, composite_score, convergence_score,
             goodhart_pressure, trajectory_drift).
    """
    fig = make_subplots(
        rows=2,
        cols=2,
        subplot_titles=["Composite Score", "Convergence Score", "Goodhart Pressure", "Trajectory Drift"],
        shared_xaxes=False,
        vertical_spacing=0.12,
        horizontal_spacing=0.1,
    )

    positions = [(1, 1), (1, 2), (2, 1), (2, 2)]
    metrics = ["composite_score", "convergence_score", "goodhart_pressure", "trajectory_drift"]

    for i, (vid, snapshots) in enumerate(series_by_variant.items()):
        color = _VARIANT_COLORS[i % len(_VARIANT_COLORS)]
        cycles = [s.get("cycle", idx) for idx, s in enumerate(snapshots)]

        for metric, (row, col) in zip(metrics, positions):
            values = [s.get(metric, 0.0) for s in snapshots]
            fig.add_trace(
                go.Scatter(
                    x=cycles,
                    y=values,
                    mode="lines+markers",
                    name=vid,
                    line={"color": color, "width": 2},
                    marker={"size": 5},
                    showlegend=(metric == "composite_score"),
                    legendgroup=vid,
                    hovertemplate=f"<b>{vid}</b><br>Cycle %{{x}}<br>{metric}: %{{y:.3f}}<extra></extra>",
                ),
                row=row,
                col=col,
            )

    fig.update_layout(
        **_base_layout(title="Per-Cycle Dynamics"),
        height=500,
    )
    fig.update_xaxes(title_text="Cycle", gridcolor=_GRID, zeroline=False)
    fig.update_yaxes(gridcolor=_GRID, zeroline=False)
    return fig


# ------------------------------------------------------------------ #
# Parallel Coordinates                                                #
# ------------------------------------------------------------------ #


def parallel_coords(
    trial_records: list[dict],
) -> go.Figure:
    """Plotly parcoords: arch params → best_score.

    Args:
        trial_records: list of dicts with keys:
            variant_id, template_count, context_injection, coherence_mode,
            embed_strategy, seed, best_score.
    """
    if not trial_records:
        fig = go.Figure()
        fig.update_layout(**_base_layout(title="Architecture Explorer"))
        return fig

    coherence_map = {"slot_ratio": 0, "length": 1, "entropy": 2}
    embed_map = {"hash": 0, "transformer": 1}

    dimensions = [
        {
            "label": "template_count",
            "values": [r.get("template_count", 4) for r in trial_records],
            "range": [1, 8],
        },
        {
            "label": "context_injection",
            "values": [int(r.get("context_injection", True)) for r in trial_records],
            "range": [0, 1],
            "tickvals": [0, 1],
            "ticktext": ["False", "True"],
        },
        {
            "label": "coherence_mode",
            "values": [coherence_map.get(r.get("coherence_mode", "slot_ratio"), 0) for r in trial_records],
            "range": [0, 2],
            "tickvals": [0, 1, 2],
            "ticktext": ["slot_ratio", "length", "entropy"],
        },
        {
            "label": "embed_strategy",
            "values": [embed_map.get(r.get("embed_strategy", "hash"), 0) for r in trial_records],
            "range": [0, 1],
            "tickvals": [0, 1],
            "ticktext": ["hash", "transformer"],
        },
        {
            "label": "best_score",
            "values": [r.get("best_score", 0.0) for r in trial_records],
            "range": [1.0, 5.0],
        },
    ]

    scores = [r.get("best_score", 0.0) for r in trial_records]

    fig = go.Figure(data=go.Parcoords(
        line={
            "color": scores,
            "colorscale": "Viridis",
            "showscale": True,
            "cmin": 1.0,
            "cmax": 5.0,
            "colorbar": {"title": "Best Score", "tickfont": {"color": _TEXT}},
        },
        dimensions=[
            go.parcoords.Dimension(**{k: v for k, v in d.items() if k != "tickvals" and k != "ticktext"})
            if "tickvals" not in d
            else go.parcoords.Dimension(
                label=d["label"],
                values=d["values"],
                range=d["range"],
                tickvals=d["tickvals"],
                ticktext=d["ticktext"],
            )
            for d in dimensions
        ],
        labelangle=15,
        labelside="bottom",
    ))

    fig.update_layout(
        **_base_layout(title="Architecture Parameter Space"),
        height=420,
    )
    return fig


# ------------------------------------------------------------------ #
# Radar                                                               #
# ------------------------------------------------------------------ #


def radar(
    summaries: list[dict],
) -> go.Figure:
    """Radar chart: 5 normalized metrics per variant.

    Args:
        summaries: list of dicts with keys:
            variant_id, best_score, mean_score, final_convergence,
            goodhart_total, total_cycles.
    """
    categories = ["best_score", "mean_score", "convergence", "novelty", "efficiency"]
    fig = go.Figure()

    for i, s in enumerate(summaries):
        color = _VARIANT_COLORS[i % len(_VARIANT_COLORS)]
        vid = s.get("variant_id", f"variant_{i}")

        # Normalize each metric to [0, 1] in approximate known ranges
        best = min(s.get("best_score", 0.0) / 5.0, 1.0)
        mean = min(s.get("mean_score", 0.0) / 5.0, 1.0)
        conv = min(s.get("final_convergence", 0.0), 1.0)
        # Novelty: invert goodhart (less Goodhart = more novelty)
        goodhart = s.get("goodhart_total", 0)
        novelty = max(0.0, 1.0 - goodhart / max(s.get("total_cycles", 1), 1))
        # Efficiency: cycles used vs ceiling (fewer = better if score is high)
        cycles = s.get("total_cycles", 1)
        efficiency = best * (1.0 - min(cycles / 10.0, 1.0) * 0.3)

        values = [best, mean, conv, novelty, efficiency]
        values_closed = values + [values[0]]

        fig.add_trace(go.Scatterpolar(
            r=values_closed,
            theta=categories + [categories[0]],
            fill="toself",
            name=vid,
            line={"color": color, "width": 2},
            fillcolor=color,
            opacity=0.25,
            hovertemplate="<b>" + vid + "</b><br>%{theta}: %{r:.2f}<extra></extra>",
        ))

    fig.update_layout(
        **_base_layout(title="Variant Comparison Radar"),
        polar={
            "bgcolor": _SURFACE,
            "radialaxis": {
                "visible": True,
                "range": [0, 1],
                "gridcolor": _GRID,
                "tickfont": {"color": _SUBTEXT, "size": 10},
            },
            "angularaxis": {
                "gridcolor": _GRID,
                "tickfont": {"color": _TEXT, "size": 11},
            },
        },
        showlegend=True,
    )
    return fig


# ------------------------------------------------------------------ #
# Leaderboard table helper                                            #
# ------------------------------------------------------------------ #


def leaderboard_table(summaries: list[dict]) -> go.Figure:
    """Simple table figure sorted by best_score desc."""
    if not summaries:
        return go.Figure()

    sorted_s = sorted(summaries, key=lambda x: x.get("best_score", 0.0), reverse=True)
    rows = {
        "Variant": [s.get("variant_id", "?") for s in sorted_s],
        "Best": [f"{s.get('best_score', 0.0):.3f}" for s in sorted_s],
        "Mean": [f"{s.get('mean_score', 0.0):.3f}" for s in sorted_s],
        "Conv.": [f"{s.get('final_convergence', 0.0):.3f}" for s in sorted_s],
        "Goodhart": [str(s.get("goodhart_total", 0)) for s in sorted_s],
        "Cycles": [str(s.get("total_cycles", 0)) for s in sorted_s],
        "Halt": [s.get("halt_reason", "")[:20] for s in sorted_s],
    }

    header_color = "#7C3AED"
    cell_colors = [_SURFACE] * len(sorted_s)

    fig = go.Figure(data=go.Table(
        header={
            "values": list(rows.keys()),
            "fill_color": header_color,
            "font": {"color": "white", "size": 12},
            "align": "left",
            "height": 30,
        },
        cells={
            "values": list(rows.values()),
            "fill_color": _SURFACE,
            "font": {"color": _TEXT, "size": 11},
            "align": "left",
            "height": 26,
            "line_color": _GRID,
        },
    ))
    fig.update_layout(
        **_base_layout(title="Leaderboard", margin={"l": 10, "r": 10, "t": 40, "b": 10}),
        height=min(200 + len(sorted_s) * 30, 420),
    )
    return fig

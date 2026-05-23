"""Q2 — WHAT: Live Dynamics panel.

Real-time score evolution, per-cycle dynamics curves, leaderboard table,
and architecture comparison radar.
"""

from __future__ import annotations

import streamlit as st

from frontend.charts import (
    dynamics_curves,
    leaderboard_table,
    radar,
    score_evolution,
)
from frontend.state import LoopState


def render(state: LoopState) -> None:
    """Render the Q2 panel from current LoopState."""
    st.markdown("### Q2 — WHAT: Live Dynamics")
    st.markdown(
        "_Score trajectories and convergence metrics update after each iteration. "
        "The loop is running in a background thread._"
    )

    if not state.iteration_results:
        st.info("Waiting for first iteration to complete…")
        _empty_placeholders()
        return

    # ── Status banner ─────────────────────────────────────────────────
    _status_banner(state)

    # ── Score evolution ───────────────────────────────────────────────
    st.markdown("#### Score evolution")
    fig_evo = score_evolution(state.summaries_by_iteration())
    st.plotly_chart(fig_evo, use_container_width=True, config={"displayModeBar": False})

    # ── Two-column: radar + leaderboard ───────────────────────────────
    col_left, col_right = st.columns([1, 1])

    latest = state.latest_summaries()
    with col_left:
        st.markdown("#### Variant radar")
        if latest:
            st.plotly_chart(
                radar(latest),
                use_container_width=True,
                config={"displayModeBar": False},
            )
        else:
            st.empty()

    with col_right:
        st.markdown("#### Leaderboard")
        if latest:
            st.plotly_chart(
                leaderboard_table(latest),
                use_container_width=True,
                config={"displayModeBar": False},
            )
        else:
            st.empty()

    # ── Per-cycle dynamics ────────────────────────────────────────────
    series = state.series_by_variant()
    if series:
        st.markdown("#### Per-iteration dynamics")
        st.plotly_chart(
            dynamics_curves(series),
            use_container_width=True,
            config={"displayModeBar": False},
        )

    # ── Best candidate text ───────────────────────────────────────────
    if latest:
        best_s = max(latest, key=lambda s: s.get("best_score", 0.0))
        candidate = best_s.get("best_candidate", "")
        if candidate:
            st.markdown("#### Best candidate this iteration")
            st.info(candidate)


# ------------------------------------------------------------------ #
# Internal helpers                                                    #
# ------------------------------------------------------------------ #


def _status_banner(state: LoopState) -> None:
    n_iters = len(state.iteration_results)
    latest = state.latest_summaries()
    best_score = max((s.get("best_score", 0.0) for s in latest), default=0.0)

    cols = st.columns(4)
    with cols[0]:
        st.metric("Status", state.status.upper())
    with cols[1]:
        st.metric("Iterations", n_iters)
    with cols[2]:
        st.metric("Best score", f"{best_score:.3f}")
    with cols[3]:
        hyp = state.hypothesis
        criterion = hyp.stopping_criterion if hyp else "—"
        st.metric("Stopping", criterion)


def _empty_placeholders() -> None:
    """Show skeleton UI before any data arrives."""
    st.markdown("#### Score evolution")
    st.empty()
    col_left, col_right = st.columns(2)
    with col_left:
        st.markdown("#### Variant radar")
        st.empty()
    with col_right:
        st.markdown("#### Leaderboard")
        st.empty()

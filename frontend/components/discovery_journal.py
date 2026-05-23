"""Q4 — IF: Discovery Journal panel.

Claude's findings per iteration, mid-loop variant injection form,
Architecture Explorer (cross-run scatter from ledger), and export.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import streamlit as st

from frontend.charts import parallel_coords
from frontend.state import LoopState


def render(state: LoopState, runner) -> None:
    """Render the Q4 panel.

    Args:
        state:  Current LoopState.
        runner: BackgroundRunner instance (for inject_variant access).
    """
    st.markdown("### Q4 — IF: Discovery Journal")
    st.markdown(
        "_Claude's design reasoning per iteration, the cross-run architecture explorer, "
        "and experiment export tools._"
    )

    tab_findings, tab_explorer, tab_export = st.tabs(
        ["Findings & Reasoning", "Architecture Explorer", "Export"]
    )

    with tab_findings:
        _render_findings(state)

    with tab_explorer:
        _render_architecture_explorer(state)

    with tab_export:
        _render_export(state)


# ------------------------------------------------------------------ #
# Findings                                                            #
# ------------------------------------------------------------------ #


_PERSONA_COLORS = {
    "Research Scientist": "#2563EB",
    "Deployed Engineer":  "#059669",
    "Chaos Engineer":     "#DC2626",
}


def _render_findings(state: LoopState) -> None:
    if not state.iteration_results:
        st.info("No findings yet. Start an experiment to see Claude's reasoning here.")
        return

    hyp = state.hypothesis
    if hyp:
        st.markdown(f"**Question:** {hyp.question}")
        st.markdown(f"**Predicted outcome:** {hyp.predicted_outcome}")
        if getattr(hyp, 'panel', None):
            personas = ", ".join(f"`{p.name}`" for p in hyp.panel)
            st.markdown(f"**Panel:** {personas}")
        st.markdown("---")

    for r in reversed(state.iteration_results):
        hyp_snap = r.hypothesis_snapshot
        findings = hyp_snap.get("findings", [])
        finding = findings[-1] if findings else "(no finding)"
        is_latest = r.iteration == state.iteration_results[-1].iteration

        with st.expander(f"Iteration {r.iteration}", expanded=is_latest):
            st.markdown(f"**Finding:** {finding}")

            # Show deltas if comparison has them
            deltas = r.comparison.get("deltas", {})
            if deltas:
                st.markdown("**Deltas vs. baseline:**")
                delta_lines = [f"- `{k}`: `{v:+.4f}`" for k, v in deltas.items()]
                st.markdown("\n".join(delta_lines))

            # Best candidate
            best_s = max(r.summaries, key=lambda s: s.get("best_score", 0.0), default=None)
            if best_s:
                st.markdown(
                    f"**Winner:** `{best_s.get('variant_id', '?')}` "
                    f"(score `{best_s.get('best_score', 0.0):.3f}`)"
                )
                candidate = best_s.get("best_candidate", "")
                if candidate:
                    st.caption(f"Best candidate: {candidate}")

            # ── Panel deliberation ────────────────────────────────────
            if r.panel_proposals:
                st.markdown("---")
                st.markdown("**Panel deliberation**")
                _render_panel_proposals(r.panel_proposals)

    # ── Resolution ────────────────────────────────────────────────────
    if state.status == "complete" and state.resolution:
        st.success(f"Loop complete: {state.resolution}")


def _render_panel_proposals(proposals: list[dict]) -> None:
    """Render each persona's reasoning + proposed variants."""
    cols = st.columns(len(proposals))
    for col, p in zip(cols, proposals):
        persona = p.get("persona", "Unknown")
        color = _PERSONA_COLORS.get(persona, "#7C3AED")
        confidence = p.get("confidence", 0.5)
        reasoning = p.get("reasoning", "")
        variants = p.get("variants", [])

        with col:
            st.markdown(
                f"<div style='border-left:3px solid {color};padding-left:10px'>"
                f"<b style='color:{color}'>{persona}</b><br>"
                f"<small>confidence: {confidence:.2f}</small>"
                f"</div>",
                unsafe_allow_html=True,
            )
            st.caption(reasoning)
            for v in variants:
                vid = v.get("variant_id", "?")
                desc = v.get("description", "")
                params = v.get("params", {})
                st.markdown(f"→ `{vid}`: {desc}")
                if params:
                    param_str = " | ".join(f"{k}={val}" for k, val in params.items())
                    st.caption(param_str)


# ------------------------------------------------------------------ #
# Architecture Explorer                                               #
# ------------------------------------------------------------------ #


def _render_architecture_explorer(state: LoopState) -> None:
    st.markdown("#### Cross-run parameter space")
    st.markdown(
        "Reads `logs/experiment_ledger.jsonl` plus current session data to show "
        "how parameters map to best_score across ALL past experiments."
    )

    records = _load_ledger_records()
    # Merge in current session data
    records.extend(state.all_trial_records())

    if not records:
        st.info("No ledger data found. Run experiments to populate the explorer.")
        return

    fig = parallel_coords(records)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": True})

    st.markdown(f"_{len(records)} trial records from ledger + current session._")

    # Searchable table
    with st.expander("View raw records"):
        st.dataframe(records, use_container_width=True)


def _load_ledger_records() -> list[dict]:
    ledger_path = Path("logs/experiment_ledger.jsonl")
    records: list[dict] = []
    if not ledger_path.exists():
        return records
    try:
        with open(ledger_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    trace = json.loads(line)
                    sr = trace.get("simulation_result", {})
                    ds = trace.get("dynamics_summary", {})
                    config = trace.get("config", {})
                    records.append({
                        "variant_id": trace.get("architecture_id", "?"),
                        "iteration": 0,
                        "best_score": float(sr.get("best_score", 0.0)),
                        "template_count": config.get("template_count", 4),
                        "context_injection": config.get("context_injection", True),
                        "coherence_mode": config.get("coherence_mode", "slot_ratio"),
                        "embed_strategy": config.get("embed_strategy", "hash"),
                        "seed": config.get("seed", 42),
                    })
                except (json.JSONDecodeError, KeyError):
                    continue
    except OSError:
        pass
    return records


# ------------------------------------------------------------------ #
# Export                                                              #
# ------------------------------------------------------------------ #


def _render_export(state: LoopState) -> None:
    st.markdown("#### Export findings")

    if not state.iteration_results:
        st.info("No data to export yet.")
        return

    # Markdown export
    if st.button("Export findings as Markdown"):
        md = _build_markdown_report(state)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"discovery_{ts}.md"
        st.download_button(
            label="Download Markdown",
            data=md,
            file_name=fname,
            mime="text/markdown",
        )

    # JSON export
    if state.hypothesis and st.button("Export hypothesis state as JSON"):
        hyp_json = json.dumps(state.hypothesis.to_dict(), indent=2)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.download_button(
            label="Download JSON",
            data=hyp_json,
            file_name=f"hypothesis_{state.hypothesis.hypothesis_id}_{ts}.json",
            mime="application/json",
        )


def _build_markdown_report(state: LoopState) -> str:
    hyp = state.hypothesis
    lines = [
        f"# Discovery Report",
        f"",
        f"**Question:** {hyp.question if hyp else 'N/A'}",
        f"**Predicted outcome:** {hyp.predicted_outcome if hyp else 'N/A'}",
        f"**Status:** {state.status}",
        f"**Resolution:** {state.resolution or '(in progress)'}",
        f"",
        f"## Findings by Iteration",
        f"",
    ]
    for r in state.iteration_results:
        hyp_snap = r.hypothesis_snapshot
        findings = hyp_snap.get("findings", [])
        finding = findings[-1] if findings else "(no finding)"
        lines.append(f"### Iteration {r.iteration}")
        lines.append(f"")
        lines.append(f"**Finding:** {finding}")
        lines.append(f"")
        if r.summaries:
            lines.append("| Variant | Best | Mean | Conv | Goodhart |")
            lines.append("|---------|------|------|------|----------|")
            for s in sorted(r.summaries, key=lambda x: x.get("best_score", 0.0), reverse=True):
                lines.append(
                    f"| {s.get('variant_id', '?')} "
                    f"| {s.get('best_score', 0.0):.3f} "
                    f"| {s.get('mean_score', 0.0):.3f} "
                    f"| {s.get('final_convergence', 0.0):.3f} "
                    f"| {s.get('goodhart_total', 0)} |"
                )
        lines.append(f"")

    return "\n".join(lines)

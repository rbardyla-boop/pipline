"""Q3 — HOW: Variant Controls panel.

Fine-grained parameter controls per variant while the loop is running.
Supports mid-loop injection and "clone best + vary" shortcuts.
"""

from __future__ import annotations

import streamlit as st

from uaf.research.hypothesis import VariantSpec


_COHERENCE_MODES = ["slot_ratio", "length", "entropy"]
_EMBED_STRATEGIES = ["hash", "transformer"]


def render(
    summaries: list[dict],
    inject_fn,
) -> None:
    """Render the Q3 panel.

    Args:
        summaries:  Latest TrialSummary dicts (variant_id, best_score, …).
        inject_fn:  Callable[[VariantSpec], None] — injects a new variant into
                    the running BackgroundRunner for the next iteration.
    """
    st.markdown("### Q3 — HOW: Variant Controls")
    st.markdown(
        "_Tune parameters for the next iteration, inject new variants mid-loop, "
        "or clone the best performer to explore a single axis._"
    )

    if not summaries:
        st.info("Run an experiment to see live variant controls here.")
        return

    best = max(summaries, key=lambda s: s.get("best_score", 0.0))
    best_vid = best.get("variant_id", "")

    # ── Clone-best shortcuts ──────────────────────────────────────────
    st.markdown("#### Quick actions")
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Clone best + vary template_count", use_container_width=True):
            _clone_and_vary(best, "template_count", [1, 4, 8], inject_fn)
            st.success("Injected 3 variants varying template_count")

    with col2:
        if st.button("Clone best + vary coherence_mode", use_container_width=True):
            _clone_and_vary(best, "coherence_mode", _COHERENCE_MODES, inject_fn)
            st.success("Injected 3 variants varying coherence_mode")

    with col3:
        if st.button("Clone best + flip context_injection", use_container_width=True):
            params = _best_params(best)
            flipped = not params.get("context_injection", True)
            spec = VariantSpec(
                variant_id=f"inject_ci_{int(flipped)}",
                description=f"clone of {best_vid} with context_injection={flipped}",
                arch_type="parametric",
                params={**params, "context_injection": flipped},
            )
            inject_fn(spec)
            st.success(f"Injected: context_injection={flipped}")

    # ── Manual injection ──────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Inject a custom variant")

    with st.expander("Custom variant builder", expanded=False):
        ic1, ic2 = st.columns(2)
        with ic1:
            inj_id = st.text_input("variant_id", value="inject_custom_1", key="inj_vid")
            inj_desc = st.text_input("description", value="custom injection", key="inj_desc")
            inj_arch = st.selectbox("arch_type", ["parametric", "symbolic_grammar"], key="inj_arch")
        with ic2:
            inj_tc = st.slider("template_count", 1, 8, 4, key="inj_tc")
            inj_ci = st.toggle("context_injection", value=True, key="inj_ci")
            inj_cm = st.selectbox("coherence_mode", _COHERENCE_MODES, key="inj_cm")
            inj_em = st.selectbox("embed_strategy", _EMBED_STRATEGIES, key="inj_em")
            inj_seed = st.number_input("seed", value=99, key="inj_seed")

        if st.button("Inject into next iteration", type="primary"):
            spec = VariantSpec(
                variant_id=inj_id,
                description=inj_desc,
                arch_type=inj_arch,
                params={
                    "template_count": inj_tc,
                    "context_injection": inj_ci,
                    "coherence_mode": inj_cm,
                    "embed_strategy": inj_em,
                    "seed": inj_seed,
                } if inj_arch == "parametric" else {"seed": inj_seed},
            )
            inject_fn(spec)
            st.success(f"Queued `{inj_id}` for injection.")

    # ── Per-variant summary cards ─────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Current variant scores")

    sorted_s = sorted(summaries, key=lambda s: s.get("best_score", 0.0), reverse=True)
    for s in sorted_s:
        vid = s.get("variant_id", "?")
        best_score = s.get("best_score", 0.0)
        is_winner = vid == best_vid

        badge = "🥇 " if is_winner else ""
        with st.container():
            st.markdown(
                f"**{badge}{vid}** — best: `{best_score:.3f}` | "
                f"mean: `{s.get('mean_score', 0.0):.3f}` | "
                f"conv: `{s.get('final_convergence', 0.0):.3f}` | "
                f"goodhart: `{s.get('goodhart_total', 0)}`"
            )
            # Candidate preview
            candidate = s.get("best_candidate", "")
            if candidate:
                st.caption(f"› {candidate[:140]}")


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #


def _best_params(summary: dict) -> dict:
    return {
        "template_count": summary.get("template_count", 4),
        "context_injection": summary.get("context_injection", True),
        "coherence_mode": summary.get("coherence_mode", "slot_ratio"),
        "embed_strategy": summary.get("embed_strategy", "hash"),
        "seed": summary.get("seed", 42),
    }


def _clone_and_vary(
    best_summary: dict,
    param: str,
    values: list,
    inject_fn,
) -> None:
    base = _best_params(best_summary)
    vid = best_summary.get("variant_id", "best")
    for i, val in enumerate(values):
        spec = VariantSpec(
            variant_id=f"inject_{param}_{i + 1}",
            description=f"clone of {vid} with {param}={val}",
            arch_type="parametric",
            params={**base, param: val},
        )
        inject_fn(spec)

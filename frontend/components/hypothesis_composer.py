"""Q1 — WHY: Hypothesis Composer panel.

Lets the user define the research question, seeds, domain, stopping criterion,
and either fill variant specs manually or let Claude generate them.
Returns a Hypothesis object ready to hand to BackgroundRunner.start().
"""

from __future__ import annotations

import os

import streamlit as st
import yaml

from uaf.research.hypothesis import Hypothesis, VariantSpec


_DEFAULT_SEEDS = (
    "a mystery game where memory works backwards,"
    "a survival game where sacrifice is the economy,"
    "a horror game with procedurally generated grief"
)

_STOPPING_OPTIONS = {
    "max_iterations": "Run for N iterations then stop",
    "score_threshold": "Stop when best score ≥ target",
    "hypothesis_confirmed": "Claude decides when it's answered",
}


def render() -> Hypothesis | None:
    """Render the Q1 panel; returns a Hypothesis when the user clicks Run, else None."""
    st.markdown("### Q1 — WHY: Define Your Research Hypothesis")
    st.markdown(
        "_What architectural parameter do you suspect changes discovery quality? "
        "Formulate your hypothesis here, configure variants, and launch._"
    )

    col_left, col_right = st.columns([2, 1])

    with col_left:
        question = st.text_area(
            "Research question",
            value="Does template_count affect the diversity and quality of generated concepts?",
            height=80,
            help="What you want the experiment to answer.",
        )

        predicted_outcome = st.text_input(
            "Predicted outcome",
            value="More templates → higher diversity → higher best_score",
            help="Your hypothesis before running. Claude will compare results against this.",
        )

        seeds_raw = st.text_area(
            "Seed concepts (one per line or comma-separated)",
            value=_DEFAULT_SEEDS.replace(",", "\n"),
            height=100,
            help="Starting domain seeds passed to each architecture variant.",
        )

    with col_right:
        domain = st.selectbox(
            "Domain",
            ["gaming", "film", "music", "art", "fiction", "tech"],
            index=0,
        )

        max_cycles = st.number_input(
            "Cycles per variant",
            min_value=1,
            max_value=20,
            value=3,
            help="Simulation cycles each architecture runs per trial.",
        )

        stopping = st.radio(
            "Stopping criterion",
            list(_STOPPING_OPTIONS.keys()),
            format_func=lambda k: k,
            help="\n".join(f"**{k}**: {v}" for k, v in _STOPPING_OPTIONS.items()),
        )

        target_score = st.slider(
            "Target score",
            min_value=1.0,
            max_value=5.0,
            value=4.3,
            step=0.1,
            disabled=(stopping != "score_threshold"),
            help="Only active when stopping criterion is 'score_threshold'.",
        )

        max_iterations = st.number_input(
            "Max loop iterations",
            min_value=1,
            max_value=20,
            value=4,
        )

        verification = st.radio(
            "Verification mode",
            ["heuristic", "phoenix"],
            format_func=lambda m: "Heuristic (free, fast)" if m == "heuristic" else "Phoenix (real API)",
            help="Heuristic uses word-diversity scoring. Phoenix calls the ConceptRater API.",
        )

    # ── YAML / file loader ────────────────────────────────────────────
    st.markdown("---")
    col_yaml, col_gen = st.columns(2)

    with col_yaml:
        st.markdown("**Load from YAML**")
        uploaded = st.file_uploader("Upload hypothesis YAML", type=["yaml", "yml"])
        if uploaded:
            try:
                data = yaml.safe_load(uploaded.read())
                h = Hypothesis.from_dict(data)
                st.success(f"Loaded `{h.hypothesis_id}` — {len(h.variants)} variants")
                return h
            except Exception as exc:
                st.error(f"Failed to parse YAML: {exc}")

    with col_gen:
        st.markdown("**Auto-generate starting variants via Claude**")
        n_variants = st.number_input("Number of variants", min_value=2, max_value=6, value=3)
        gen_btn = st.button("Generate variants with Claude", use_container_width=True)

    # ── Manual variant editor ─────────────────────────────────────────
    st.markdown("---")
    st.markdown("**Or configure variants manually**")

    variants = _variant_editor()

    # ── Launch ───────────────────────────────────────────────────────
    st.markdown("---")
    launch = st.button("▶  Run Experiment", type="primary", use_container_width=True)

    if gen_btn or launch:
        seeds = [s.strip() for s in seeds_raw.replace("\n", ",").split(",") if s.strip()]

        if gen_btn and not launch:
            variants = _generate_variants_via_claude(question, domain, n_variants)
            if not variants:
                return None

        if not variants:
            st.warning("Add at least one variant before launching.")
            return None

        hyp_id = f"exp_{abs(hash(question)) % 100000:05d}"
        return Hypothesis(
            hypothesis_id=hyp_id,
            question=question,
            predicted_outcome=predicted_outcome,
            domain=domain,
            seeds=seeds,
            variants=variants,
            max_cycles=int(max_cycles),
            stopping_criterion=stopping,
            target_score=float(target_score),
            verification_mode=verification,
        )

    return None


# ------------------------------------------------------------------ #
# Manual variant editor                                               #
# ------------------------------------------------------------------ #


def _variant_editor() -> list[VariantSpec]:
    """Inline variant config rows with Add/Remove buttons."""
    if "composer_variants" not in st.session_state:
        st.session_state.composer_variants = [
            {"variant_id": "iter1_v1", "description": "baseline 4 templates", "arch_type": "parametric",
             "params": {"template_count": 4, "context_injection": False, "coherence_mode": "slot_ratio",
                        "embed_strategy": "hash", "seed": 42}},
            {"variant_id": "iter1_v2", "description": "full pool + context", "arch_type": "parametric",
             "params": {"template_count": 8, "context_injection": True, "coherence_mode": "slot_ratio",
                        "embed_strategy": "hash", "seed": 42}},
        ]

    variants_data = st.session_state.composer_variants
    to_remove = None

    for idx, vd in enumerate(variants_data):
        with st.expander(f"Variant {idx + 1}: `{vd['variant_id']}`", expanded=(idx == 0)):
            c1, c2, c3 = st.columns([2, 2, 1])
            with c1:
                vd["variant_id"] = st.text_input(
                    "variant_id", value=vd["variant_id"], key=f"vid_{idx}"
                )
                vd["description"] = st.text_input(
                    "description", value=vd["description"], key=f"desc_{idx}"
                )
            with c2:
                vd["arch_type"] = st.selectbox(
                    "arch_type",
                    ["parametric", "symbolic_grammar"],
                    index=0 if vd["arch_type"] == "parametric" else 1,
                    key=f"arch_{idx}",
                )
            with c3:
                if st.button("Remove", key=f"rm_{idx}"):
                    to_remove = idx

            if vd["arch_type"] == "parametric":
                p = vd["params"]
                pc1, pc2, pc3 = st.columns(3)
                with pc1:
                    p["template_count"] = st.slider(
                        "template_count", 1, 8, p.get("template_count", 4), key=f"tc_{idx}"
                    )
                    p["seed"] = st.number_input(
                        "seed", value=p.get("seed", 42), key=f"seed_{idx}"
                    )
                with pc2:
                    p["context_injection"] = st.toggle(
                        "context_injection", value=p.get("context_injection", True), key=f"ci_{idx}"
                    )
                    p["coherence_mode"] = st.selectbox(
                        "coherence_mode",
                        ["slot_ratio", "length", "entropy"],
                        index=["slot_ratio", "length", "entropy"].index(
                            p.get("coherence_mode", "slot_ratio")
                        ),
                        key=f"cm_{idx}",
                    )
                with pc3:
                    p["embed_strategy"] = st.selectbox(
                        "embed_strategy",
                        ["hash", "transformer"],
                        index=0 if p.get("embed_strategy", "hash") == "hash" else 1,
                        key=f"em_{idx}",
                    )
            else:
                p = vd.get("params", {})
                p["seed"] = st.number_input(
                    "seed", value=p.get("seed", 42), key=f"sg_seed_{idx}"
                )
                vd["params"] = p

    if to_remove is not None:
        variants_data.pop(to_remove)
        st.rerun()

    if st.button("+ Add variant"):
        n = len(variants_data) + 1
        variants_data.append({
            "variant_id": f"iter1_v{n}",
            "description": f"variant {n}",
            "arch_type": "parametric",
            "params": {"template_count": 4, "context_injection": True,
                       "coherence_mode": "slot_ratio", "embed_strategy": "hash", "seed": n * 7},
        })
        st.rerun()

    return [
        VariantSpec(
            variant_id=vd["variant_id"],
            description=vd["description"],
            arch_type=vd["arch_type"],
            params=vd.get("params", {}),
        )
        for vd in variants_data
    ]


# ------------------------------------------------------------------ #
# Claude variant generation                                           #
# ------------------------------------------------------------------ #


def _generate_variants_via_claude(question: str, domain: str, n: int) -> list[VariantSpec]:
    import anthropic
    import json
    from dotenv import load_dotenv

    load_dotenv()
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        st.error("ANTHROPIC_API_KEY not found in environment.")
        return []

    client = anthropic.Anthropic(api_key=api_key)
    param_docs = """Available arch_type="parametric" params:
  - template_count: int 1-8
  - context_injection: bool
  - coherence_mode: "slot_ratio" | "length" | "entropy"
  - embed_strategy: "hash" | "transformer"
  - seed: int"""

    prompt = f"""Research question: {question}\nDomain: {domain}\n\n{param_docs}\n
Design {n} parametric variants that maximally span the parameter space for answering this question.
Respond ONLY with a valid JSON array, no markdown:
[{{"variant_id":"iter1_v1","description":"...","arch_type":"parametric","params":{{...}}}}]"""

    with st.spinner("Asking Claude to design starting variants..."):
        try:
            resp = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = resp.content[0].text.strip()
            if raw.startswith("```"):
                parts = raw.split("```")
                raw = parts[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            specs = [VariantSpec.from_dict(d) for d in json.loads(raw.strip())]
            st.success(f"Claude designed {len(specs)} variants.")
            return specs
        except Exception as exc:
            st.error(f"Claude generation failed: {exc}")
            return []

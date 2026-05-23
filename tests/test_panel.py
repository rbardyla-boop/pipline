"""Tests for the parallel engineer panel deliberation layer.

All Claude API calls are mocked — no real API calls, no network I/O.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, call, patch

import pytest

from uaf.research.hypothesis import (
    Hypothesis,
    PanelProposal,
    PersonaSpec,
    TrialSummary,
    VariantSpec,
)
from uaf.research.panel import DEFAULT_PERSONAS, EngineerPanel


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #


def _make_persona(name: str = "Research Scientist") -> PersonaSpec:
    return PersonaSpec(
        name=name,
        lens="Test lens.",
        what_if_bias="Test bias.",
    )


def _make_summaries() -> list[TrialSummary]:
    return [
        TrialSummary(
            variant_id="iter1_v1",
            architecture_id="iter1_v1",
            best_score=4.5,
            mean_score=3.8,
            final_convergence=0.9,
            trajectory_drift=0.0,
            goodhart_total=0,
            halt_reason="max_loops_reached",
            total_cycles=4,
            best_candidate="The cascade of entropy: a ritual that inverts.",
        ),
        TrialSummary(
            variant_id="iter1_v2",
            architecture_id="iter1_v2",
            best_score=3.8,
            mean_score=3.5,
            final_convergence=0.7,
            trajectory_drift=0.0,
            goodhart_total=0,
            halt_reason="max_loops_reached",
            total_cycles=4,
            best_candidate="A sacrifice protocol that crystallizes under friction.",
        ),
    ]


def _make_hypothesis(panel: list[PersonaSpec] | None = None) -> Hypothesis:
    return Hypothesis(
        hypothesis_id="panel_test",
        question="Does coherence_mode affect mean_score?",
        predicted_outcome="entropy mode scores higher",
        domain="gaming",
        seeds=["a sacrifice game"],
        variants=[
            VariantSpec("iter1_v1", "slot_ratio", "parametric",
                        {"template_count": 4, "coherence_mode": "slot_ratio", "seed": 42}),
            VariantSpec("iter1_v2", "entropy", "parametric",
                        {"template_count": 4, "coherence_mode": "entropy", "seed": 42}),
        ],
        max_cycles=3,
        panel=panel,
    )


def _persona_response(persona_name: str, iter_num: int) -> dict:
    prefix = persona_name[:3].lower()
    return {
        "persona": persona_name,
        "reasoning": f"From the {persona_name} lens, we should test X.",
        "confidence": 0.75,
        "variants": [
            {
                "variant_id": f"iter{iter_num}_{prefix}_v1",
                "description": f"{persona_name} variant 1",
                "arch_type": "parametric",
                "params": {"template_count": 4, "coherence_mode": "slot_ratio",
                           "context_injection": False, "seed": 10},
            },
            {
                "variant_id": f"iter{iter_num}_{prefix}_v2",
                "description": f"{persona_name} variant 2",
                "arch_type": "parametric",
                "params": {"template_count": 6, "coherence_mode": "entropy",
                           "context_injection": True, "seed": 20},
            },
        ],
    }


def _synthesis_response(iter_num: int) -> list[dict]:
    return [
        {
            "variant_id": f"iter{iter_num}_syn_v1",
            "description": "synthesis pick 1",
            "arch_type": "parametric",
            "params": {"template_count": 4, "coherence_mode": "slot_ratio", "seed": 1},
        },
        {
            "variant_id": f"iter{iter_num}_syn_v2",
            "description": "synthesis pick 2",
            "arch_type": "parametric",
            "params": {"template_count": 6, "coherence_mode": "entropy", "seed": 2},
        },
        {
            "variant_id": f"iter{iter_num}_syn_v3",
            "description": "synthesis pick 3",
            "arch_type": "parametric",
            "params": {"template_count": 8, "coherence_mode": "length", "seed": 3},
        },
    ]


def _build_mock_client(personas: list[PersonaSpec], iter_num: int = 1) -> MagicMock:
    """Build a mock client that returns persona responses then synthesis."""
    client = MagicMock()
    responses = []
    for p in personas:
        responses.append(
            MagicMock(content=[MagicMock(text=json.dumps(_persona_response(p.name, iter_num)))])
        )
    # Synthesis call last
    responses.append(
        MagicMock(content=[MagicMock(text=json.dumps(_synthesis_response(iter_num)))])
    )
    client.messages.create.side_effect = responses
    return client


# ------------------------------------------------------------------ #
# PersonaSpec                                                         #
# ------------------------------------------------------------------ #


def test_persona_spec_round_trips():
    p = _make_persona("Chaos Engineer")
    d = p.to_dict()
    restored = PersonaSpec.from_dict(d)
    assert restored.name == p.name
    assert restored.lens == p.lens
    assert restored.what_if_bias == p.what_if_bias


def test_default_personas_have_required_fields():
    for p in DEFAULT_PERSONAS:
        assert p.name
        assert p.lens
        assert p.what_if_bias


# ------------------------------------------------------------------ #
# PanelProposal                                                       #
# ------------------------------------------------------------------ #


def test_panel_proposal_round_trips():
    prop = PanelProposal(
        persona="Research Scientist",
        reasoning="We should test unexplored regions.",
        variants=[
            VariantSpec("v1", "test", "parametric", {"template_count": 4}),
        ],
        confidence=0.8,
    )
    d = prop.to_dict()
    restored = PanelProposal.from_dict(d)
    assert restored.persona == prop.persona
    assert restored.reasoning == prop.reasoning
    assert restored.confidence == pytest.approx(0.8)
    assert len(restored.variants) == 1
    assert restored.variants[0].variant_id == "v1"


# ------------------------------------------------------------------ #
# Hypothesis panel fields                                             #
# ------------------------------------------------------------------ #


def test_hypothesis_panel_round_trips():
    personas = [_make_persona("Research Scientist"), _make_persona("Chaos Engineer")]
    h = _make_hypothesis(panel=personas)
    d = h.to_dict()
    restored = Hypothesis.from_dict(d)
    assert restored.panel is not None
    assert len(restored.panel) == 2
    assert restored.panel[0].name == "Research Scientist"


def test_hypothesis_no_panel_round_trips():
    h = _make_hypothesis(panel=None)
    d = h.to_dict()
    assert "panel" not in d
    restored = Hypothesis.from_dict(d)
    assert restored.panel is None


def test_hypothesis_panel_proposals_stored():
    h = _make_hypothesis()
    proposal = PanelProposal(
        persona="Research Scientist",
        reasoning="test",
        variants=[VariantSpec("v1", "d", "parametric", {})],
        confidence=0.5,
    )
    h.panel_proposals.append([proposal])
    d = h.to_dict()
    restored = Hypothesis.from_dict(d)
    assert len(restored.panel_proposals) == 1
    assert restored.panel_proposals[0][0].persona == "Research Scientist"


# ------------------------------------------------------------------ #
# EngineerPanel — deliberation                                        #
# ------------------------------------------------------------------ #


def test_panel_makes_n_plus_1_claude_calls():
    """One call per persona + one synthesis call."""
    personas = [_make_persona("Research Scientist"), _make_persona("Chaos Engineer")]
    client = _build_mock_client(personas, iter_num=2)

    h = _make_hypothesis(panel=personas)
    h.iteration = 1

    panel = EngineerPanel(personas=personas)
    variants, proposals = panel.deliberate(h, _make_summaries(), {}, client)

    assert client.messages.create.call_count == len(personas) + 1


def test_panel_returns_three_final_variants():
    personas = DEFAULT_PERSONAS
    client = _build_mock_client(personas, iter_num=2)

    h = _make_hypothesis(panel=personas)
    h.iteration = 1

    panel = EngineerPanel(personas=personas)
    variants, proposals = panel.deliberate(h, _make_summaries(), {}, client)

    assert len(variants) == 3
    for v in variants:
        assert isinstance(v, VariantSpec)


def test_panel_returns_one_proposal_per_persona():
    personas = DEFAULT_PERSONAS
    client = _build_mock_client(personas, iter_num=2)

    h = _make_hypothesis(panel=personas)
    h.iteration = 1

    panel = EngineerPanel(personas=personas)
    variants, proposals = panel.deliberate(h, _make_summaries(), {}, client)

    assert len(proposals) == len(personas)
    for prop in proposals:
        assert isinstance(prop, PanelProposal)
        assert prop.reasoning
        assert len(prop.variants) == 2


def test_panel_proposals_have_correct_persona_names():
    personas = [_make_persona("Research Scientist"), _make_persona("Deployed Engineer")]
    client = _build_mock_client(personas, iter_num=2)

    h = _make_hypothesis(panel=personas)
    h.iteration = 1

    panel = EngineerPanel(personas=personas)
    _, proposals = panel.deliberate(h, _make_summaries(), {}, client)

    names = {p.persona for p in proposals}
    assert "Research Scientist" in names
    assert "Deployed Engineer" in names


def test_panel_proposals_each_have_two_variants():
    personas = DEFAULT_PERSONAS
    client = _build_mock_client(personas, iter_num=3)

    h = _make_hypothesis(panel=personas)
    h.iteration = 2

    panel = EngineerPanel(personas=personas)
    _, proposals = panel.deliberate(h, _make_summaries(), {}, client)

    for prop in proposals:
        assert len(prop.variants) == 2


def test_panel_confidence_parsed():
    personas = [_make_persona("Chaos Engineer")]
    client = _build_mock_client(personas, iter_num=2)

    h = _make_hypothesis(panel=personas)
    h.iteration = 1

    panel = EngineerPanel(personas=personas)
    _, proposals = panel.deliberate(h, _make_summaries(), {}, client)

    assert proposals[0].confidence == pytest.approx(0.75)


# ------------------------------------------------------------------ #
# ExperimentLoop panel integration                                    #
# ------------------------------------------------------------------ #


def test_loop_uses_panel_when_set():
    """When hypothesis.panel is set, loop calls EngineerPanel.deliberate."""
    from uaf.research.loop import ExperimentLoop

    personas = DEFAULT_PERSONAS
    h = _make_hypothesis(panel=personas)
    h.stopping_criterion = "max_iterations"
    h.seeds = ["a sacrifice game", "a grief engine"]

    # Responses: 3 persona calls + 1 synthesis per iteration refinement
    # We run 2 iterations so need responses for iter 1 refinement (4 calls)
    client = MagicMock()
    single_iter_responses = []
    for p in personas:
        single_iter_responses.append(
            MagicMock(content=[MagicMock(text=json.dumps(_persona_response(p.name, 2)))])
        )
    single_iter_responses.append(
        MagicMock(content=[MagicMock(text=json.dumps(_synthesis_response(2)))])
    )
    client.messages.create.side_effect = single_iter_responses

    loop = ExperimentLoop(max_iterations=2, record_to_ledger=False, client=client, verbose=False)
    result = loop.run(h)

    # Panel should have been called (4 Claude calls for 1 refinement)
    assert client.messages.create.call_count >= len(personas) + 1
    # Panel proposals stored on hypothesis
    assert len(result.panel_proposals) >= 1


def test_loop_stores_panel_proposals_on_hypothesis():
    from uaf.research.loop import ExperimentLoop

    personas = [_make_persona("Research Scientist"), _make_persona("Chaos Engineer")]
    h = _make_hypothesis(panel=personas)
    h.stopping_criterion = "max_iterations"
    h.seeds = ["a sacrifice game"]

    client = _build_mock_client(personas, iter_num=2)

    loop = ExperimentLoop(max_iterations=2, record_to_ledger=False, client=client, verbose=False)
    result = loop.run(h)

    assert len(result.panel_proposals) == 1
    assert len(result.panel_proposals[0]) == 2  # 2 personas


# ------------------------------------------------------------------ #
# Repetition guard                                                    #
# ------------------------------------------------------------------ #


def test_repetition_guard_diversifies_duplicate_ids():
    from uaf.research.loop import ExperimentLoop

    h = _make_hypothesis()
    h.stopping_criterion = "max_iterations"
    h.seeds = ["a sacrifice game"]
    # Pre-populate iteration_summaries with the same variant IDs
    h.iteration_summaries = [
        [
            TrialSummary("iter1_v1", "iter1_v1", 4.0, 3.5, 0.9, 0.0, 0, "halt", 3),
            TrialSummary("iter1_v2", "iter1_v2", 3.5, 3.0, 0.8, 0.0, 0, "halt", 3),
        ]
    ]

    loop = ExperimentLoop(max_iterations=1, record_to_ledger=False, verbose=False)

    # Propose variants with the same IDs that were already seen
    repeat_variants = [
        VariantSpec("iter1_v1", "repeat", "parametric", {"template_count": 4, "seed": 42}),
        VariantSpec("iter1_v2", "repeat", "parametric", {"template_count": 8, "seed": 42}),
        VariantSpec("iter2_v1", "new", "parametric", {"template_count": 6, "seed": 42}),
    ]

    result = loop._apply_repetition_guard(h, repeat_variants)

    # The repeated variants should have been diversified (seed modified)
    repeated = [v for v in result if "g" in v.variant_id or v.params.get("seed", 42) != 42]
    assert len(repeated) >= 1

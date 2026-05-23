"""Hypothesis — structured research question with variant specs and trial results.

The discovery loop:
  Hypothesis → ControlledTrialRunner → ledger → compare → refine → repeat
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ------------------------------------------------------------------ #
# Panel data structures                                               #
# ------------------------------------------------------------------ #


@dataclass
class PersonaSpec:
    """One engineering persona in the parallel deliberation panel.

    Args:
        name:          Display name, e.g. "Chaos Engineer".
        lens:          1-2 sentence evaluation criteria.
        what_if_bias:  The direction this persona pushes exploration.
    """

    name: str
    lens: str
    what_if_bias: str

    def to_dict(self) -> dict:
        return {"name": self.name, "lens": self.lens, "what_if_bias": self.what_if_bias}

    @classmethod
    def from_dict(cls, d: dict) -> "PersonaSpec":
        return cls(name=d["name"], lens=d["lens"], what_if_bias=d["what_if_bias"])


@dataclass
class PanelProposal:
    """One persona's proposal from a single deliberation round.

    Args:
        persona:    Name of the persona that produced this.
        reasoning:  The "what if" explanation in the persona's voice.
        variants:   2 variant specs proposed by this persona.
        confidence: Self-reported 0-1 confidence in the proposals.
    """

    persona: str
    reasoning: str
    variants: list["VariantSpec"]
    confidence: float = 0.5

    def to_dict(self) -> dict:
        return {
            "persona": self.persona,
            "reasoning": self.reasoning,
            "variants": [v.to_dict() for v in self.variants],
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PanelProposal":
        return cls(
            persona=d["persona"],
            reasoning=d["reasoning"],
            variants=[VariantSpec.from_dict(v) for v in d.get("variants", [])],
            confidence=float(d.get("confidence", 0.5)),
        )


@dataclass
class VariantSpec:
    """Specification for one architecture variant in a controlled trial.

    Args:
        variant_id:   Unique slug, e.g. "iter1_template_4".
        description:  What this variant specifically tests.
        arch_type:    "parametric" | "symbolic_grammar" | "claude_novelty"
        params:       Constructor kwargs for the chosen arch type.
    """

    variant_id: str
    description: str
    arch_type: str
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "variant_id": self.variant_id,
            "description": self.description,
            "arch_type": self.arch_type,
            "params": self.params,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "VariantSpec":
        return cls(
            variant_id=d["variant_id"],
            description=d["description"],
            arch_type=d["arch_type"],
            params=d.get("params", {}),
        )


@dataclass
class TrialSummary:
    """Key metrics from one variant's trial run — extracted from ExperimentTrace."""

    variant_id: str
    architecture_id: str
    best_score: float
    mean_score: float
    final_convergence: float
    trajectory_drift: float
    goodhart_total: int
    halt_reason: str
    total_cycles: int
    best_candidate: str = ""

    def to_dict(self) -> dict:
        return {
            "variant_id": self.variant_id,
            "architecture_id": self.architecture_id,
            "best_score": self.best_score,
            "mean_score": self.mean_score,
            "final_convergence": self.final_convergence,
            "trajectory_drift": self.trajectory_drift,
            "goodhart_total": self.goodhart_total,
            "halt_reason": self.halt_reason,
            "total_cycles": self.total_cycles,
            "best_candidate": self.best_candidate,
        }


@dataclass
class Hypothesis:
    """A research question expressed as a controlled multi-variant trial.

    Stopping criteria (pick one):
        "max_iterations"      — stop after the loop runs N times.
        "score_threshold"     — stop when any variant hits target_score.
        "hypothesis_confirmed"— stop when Claude declares the question resolved.

    Args:
        hypothesis_id:        Unique slug, e.g. "template_complexity_v1".
        question:             Natural-language research question.
        predicted_outcome:    What you expect to find.
        domain:               Seed domain for all trials ("gaming", "film", etc.).
        seeds:                Concept seeds — identical across all variants.
        variants:             Architecture variants to run in parallel.
        max_cycles:           Simulation cycles per variant per iteration.
        stopping_criterion:   See above.
        target_score:         Phoenix score threshold (for "score_threshold" mode).
        verification_mode:    "heuristic" (free, fast) | "phoenix" (real rater, API).
        config_overrides:     Extra kwargs merged into each ExperimentDefinition config.
    """

    hypothesis_id: str
    question: str
    predicted_outcome: str
    domain: str
    seeds: list[str]
    variants: list[VariantSpec]
    max_cycles: int = 4
    stopping_criterion: str = "max_iterations"
    target_score: float = 4.5
    verification_mode: str = "heuristic"
    config_overrides: dict[str, Any] = field(default_factory=dict)

    # Optional parallel panel of engineering personas
    panel: list[PersonaSpec] | None = None

    # Updated by the loop
    iteration: int = 0
    iteration_summaries: list[list[TrialSummary]] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)
    panel_proposals: list[list[PanelProposal]] = field(default_factory=list)
    resolved: bool = False
    resolution: str = ""

    def best_score_so_far(self) -> float:
        all_scores = [
            s.best_score
            for iteration in self.iteration_summaries
            for s in iteration
        ]
        return max(all_scores) if all_scores else 0.0

    def to_dict(self) -> dict:
        d: dict = {
            "hypothesis_id": self.hypothesis_id,
            "question": self.question,
            "predicted_outcome": self.predicted_outcome,
            "domain": self.domain,
            "seeds": self.seeds,
            "variants": [v.to_dict() for v in self.variants],
            "max_cycles": self.max_cycles,
            "stopping_criterion": self.stopping_criterion,
            "target_score": self.target_score,
            "verification_mode": self.verification_mode,
            "iteration": self.iteration,
            "iteration_summaries": [
                [s.to_dict() for s in it] for it in self.iteration_summaries
            ],
            "findings": list(self.findings),
            "panel_proposals": [
                [p.to_dict() for p in round_] for round_ in self.panel_proposals
            ],
            "resolved": self.resolved,
            "resolution": self.resolution,
        }
        if self.panel is not None:
            d["panel"] = [p.to_dict() for p in self.panel]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Hypothesis":
        panel_data = d.get("panel")
        panel = [PersonaSpec.from_dict(p) for p in panel_data] if panel_data else None
        h = cls(
            hypothesis_id=d["hypothesis_id"],
            question=d["question"],
            predicted_outcome=d["predicted_outcome"],
            domain=d["domain"],
            seeds=d["seeds"],
            variants=[VariantSpec.from_dict(v) for v in d.get("variants", [])],
            max_cycles=d.get("max_cycles", 4),
            stopping_criterion=d.get("stopping_criterion", "max_iterations"),
            target_score=d.get("target_score", 4.5),
            verification_mode=d.get("verification_mode", "heuristic"),
            config_overrides=d.get("config_overrides", {}),
            panel=panel,
        )
        h.iteration = d.get("iteration", 0)
        h.findings = d.get("findings", [])
        h.panel_proposals = [
            [PanelProposal.from_dict(p) for p in round_]
            for round_ in d.get("panel_proposals", [])
        ]
        h.resolved = d.get("resolved", False)
        h.resolution = d.get("resolution", "")
        return h

    @classmethod
    def from_yaml(cls, path: str) -> "Hypothesis":
        import yaml
        with open(path) as f:
            d = yaml.safe_load(f)
        return cls.from_dict(d)

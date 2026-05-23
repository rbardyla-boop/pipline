"""ControlledTrialRunner — runs all variants in a Hypothesis under identical conditions.

Each variant gets:
  - The same seeds and domain
  - The same verification mode
  - Its own clean-room memory (no cross-variant state)
  - A fresh runtime ID

Results are recorded to the experiment ledger keyed by hypothesis_id so that
compare_traces() and best_architecture() work across all variants.
"""

from __future__ import annotations

import math
import re
from typing import Sequence

from uaf.experiments.definition import ExperimentDefinition
from uaf.experiments.ledger import ExperimentLedger
from uaf.experiments.runner import ExperimentRunner, ExperimentTrace
from uaf.interfaces.cognition import CognitionEngine
from uaf.interfaces.memory import MemorySystem
from uaf.interfaces.planner import Planner
from uaf.interfaces.runtime import RuntimeEnvironment
from uaf.interfaces.verification import VerificationEngine
from uaf.kernel.invariants import InvariantSet
from uaf.kernel.state import CycleState, SimulationContext, VerificationResult
from uaf.research.hypothesis import Hypothesis, TrialSummary, VariantSpec


# ------------------------------------------------------------------ #
# Clean-room infrastructure (no cross-variant state)                  #
# ------------------------------------------------------------------ #


class _ResearchMemory(MemorySystem):
    """Pure in-memory archive — isolated per variant, no persistence."""

    def __init__(self, novelty_threshold: float = 0.30) -> None:
        self._archive: list[dict] = []
        self._threshold = novelty_threshold

    def seed(self, items: list[str]) -> None:
        self._archive = [{"concept": item} for item in items]

    def add(
        self,
        item: str,
        embedding: Sequence[float],
        novelty: float,
        generation: int,
    ) -> None:
        if novelty > self._threshold:
            self._archive.append({
                "concept": item,
                "embedding": list(embedding),
                "novelty": novelty,
                "generation": generation,
            })

    def novelty_of(self, embedding: Sequence[float]) -> float:
        candidates = [
            e["embedding"] for e in self._archive if "embedding" in e
        ]
        if not candidates:
            return 0.90
        sims = [
            sum(a * b for a, b in zip(embedding, c))
            for c in candidates
        ]
        return max(0.0, 1.0 - max(sims))

    def retired_ids(self) -> set[str]:
        return set()

    def retire(self, item: str, score: float, combined: float, run_id: str) -> None:
        pass

    def session_snapshot(self) -> dict:
        return {
            "archive_size": len(self._archive),
            "session_embeddings": [],
            "refractory_clusters": [],
        }


class _CyclePlanner(Planner):
    """Halt after exactly max_cycles cycles."""

    def __init__(self, max_cycles: int) -> None:
        self._max = max_cycles

    def initial_action(self, ctx: SimulationContext) -> str:
        return "continue"

    def next_action(self, state: CycleState) -> str:
        return "halt" if state.cycle >= self._max - 1 else "continue"

    def should_halt(self, state: CycleState) -> bool:
        return state.cycle >= self._max - 1


class _HeuristicVerification(VerificationEngine):
    """Free, API-free scorer: word diversity + length + structure heuristics.

    Produces scores in [1.0, 5.0] so the invariant engine is happy.
    Use this for fast architecture comparison when Phoenix API is unavailable.
    """

    def score(self, candidate: str, ctx: SimulationContext) -> VerificationResult:
        words = re.findall(r'\b[a-zA-Z]{3,}\b', candidate.lower())
        unique_ratio = len(set(words)) / max(len(words), 1)
        length_score = min(len(candidate) / 150.0, 1.0)
        structure_bonus = 0.3 if any(c in candidate for c in (":", "—", "–", "•")) else 0.0

        raw = unique_ratio * 0.4 + length_score * 0.4 + structure_bonus
        composite = round(1.0 + raw * 4.0, 2)  # maps [0,1] → [1.0, 5.0]
        composite = max(1.0, min(5.0, composite))

        return VerificationResult(
            composite_score=composite,
            criteria_scores={"heuristic": composite},
            ritual_cost_score=0.0,
            anti_optimization_score=0.0,
            improvement_context="",
            goodhart_warning=False,
            verdict="HIT" if composite >= 3.5 else "SLOP",
            extended_verdict="HIT" if composite >= 3.5 else "SLOP",
        )

    def verdict(self, result: VerificationResult) -> str:
        return result.verdict


class _PhoenixVerification(VerificationEngine):
    """Real Phoenix rubric via ConceptRater — requires clovelearn_phoenix dep."""

    def __init__(self) -> None:
        from concept_rater import ConceptRater
        self._rater = ConceptRater()
        self._prev_embedding: list[float] | None = None

    def score(self, candidate: str, ctx: SimulationContext) -> VerificationResult:
        domain = ctx.config.get("domain", "unknown")
        result = self._rater.rate(candidate, domain)
        composite = float(result.get("composite_score", 2.5))
        composite = max(1.0, min(5.0, composite))
        goodhart = False
        if self._prev_embedding is not None:
            from uaf.dynamics.metrics import cosine_similarity
            from architectures.parametric.adapter import ParametricCognition
            emb = ParametricCognition(seed=0)._hash_embed(candidate)
            sim = cosine_similarity(self._prev_embedding, emb)
            goodhart = sim > 0.85
            self._prev_embedding = emb
        else:
            from architectures.parametric.adapter import ParametricCognition
            self._prev_embedding = ParametricCognition(seed=0)._hash_embed(candidate)

        verdict = result.get("verdict", "SLOP")
        return VerificationResult(
            composite_score=composite,
            criteria_scores=result.get("criteria_scores", {}),
            ritual_cost_score=float(result.get("ritual_cost_score", 0.0)),
            anti_optimization_score=float(result.get("anti_optimization_score", 0.0)),
            improvement_context=result.get("improvement_context", ""),
            goodhart_warning=goodhart,
            verdict=verdict,
            extended_verdict=verdict,
        )

    def verdict(self, result: VerificationResult) -> str:
        return result.verdict


class _ResearchRuntime(RuntimeEnvironment):
    """Minimal runtime — no Tavily calls, stable run_id per variant."""

    _CONTEXT = (
        "2026 cultural fractures: sacrifice economy, authenticity scarcity, "
        "ritual friction demand, anti-scale impulse, embodied meaning-making, "
        "epistemic drift, pre-digital nostalgia."
    )

    def __init__(self, variant_id: str) -> None:
        import uuid
        self._run_id = f"research_{variant_id}_{uuid.uuid4().hex[:6]}"

    def ingest_context(self, domain: str) -> str:
        return f"Domain: {domain}. {self._CONTEXT}"

    def secure_call(self, fn, *args, **kwargs):
        return fn(*args, **kwargs)

    def persist(self, key: str, payload: dict) -> None:
        pass

    def run_id(self) -> str:
        return self._run_id


# ------------------------------------------------------------------ #
# Arch instantiation                                                  #
# ------------------------------------------------------------------ #


def _instantiate_arch(spec: VariantSpec, config: dict | None = None) -> CognitionEngine:
    """Build a CognitionEngine from a VariantSpec."""
    if spec.arch_type == "parametric":
        from architectures.parametric.adapter import ParametricCognition
        return ParametricCognition(variant_id=spec.variant_id, **spec.params)

    if spec.arch_type == "symbolic_grammar":
        from architectures.symbolic_grammar.adapter import SymbolicGrammarCognition
        return SymbolicGrammarCognition(**spec.params)

    if spec.arch_type == "claude_novelty":
        from engine import NoveltySearchEngine
        from architectures.claude_novelty.adapter import ClaudeNoveltyCognition
        engine = NoveltySearchEngine()
        return ClaudeNoveltyCognition(engine)

    if spec.arch_type == "neural_transformer":
        from architectures.neural.adapter import NeuralTransformerCognition
        seeds = (config or {}).get("seeds", [])
        return NeuralTransformerCognition(seeds=seeds, **spec.params)

    raise ValueError(f"Unknown arch_type: {spec.arch_type!r}")


# ------------------------------------------------------------------ #
# Controlled trial runner                                             #
# ------------------------------------------------------------------ #


class ControlledTrialRunner:
    """Runs every variant in a Hypothesis under identical conditions.

    All variants share:
      - Same seeds, domain, and config
      - Same max_cycles
      - Same verification mode

    Each variant gets its own:
      - Architecture instance (fresh)
      - Memory instance (clean-room)
      - Runtime (unique run_id)

    Results are appended to the experiment ledger under hypothesis_id.
    """

    def __init__(self, record_to_ledger: bool = True) -> None:
        self._record = record_to_ledger
        self._ledger = ExperimentLedger() if record_to_ledger else None

    def run(self, hypothesis: Hypothesis) -> list[ExperimentTrace]:
        """Execute all variants and return traces in spec order."""
        config = {
            "domain": hypothesis.domain,
            "seeds": hypothesis.seeds,
            "max_cycles": hypothesis.max_cycles,
            **hypothesis.config_overrides,
        }

        verification = self._make_verification(hypothesis.verification_mode)
        traces: list[ExperimentTrace] = []

        for spec in hypothesis.variants:
            print(
                f"  [{spec.variant_id}] {spec.description} "
                f"({spec.arch_type}: {spec.params})"
            )
            arch = _instantiate_arch(spec, config=config)
            defn = ExperimentDefinition(
                experiment_id=hypothesis.hypothesis_id,
                architecture=arch,
                memory=_ResearchMemory(),
                planner=_CyclePlanner(hypothesis.max_cycles),
                verification=verification,
                runtime=_ResearchRuntime(spec.variant_id),
                invariants=InvariantSet.default(),
                config=config,
            )
            trace = ExperimentRunner().execute(defn)
            traces.append(trace)

            if self._ledger:
                self._ledger.record(trace)

        return traces

    @staticmethod
    def _make_verification(mode: str) -> VerificationEngine:
        if mode == "phoenix":
            return _PhoenixVerification()
        return _HeuristicVerification()

    @staticmethod
    def summaries_from_traces(
        variants: list[VariantSpec],
        traces: list[ExperimentTrace],
    ) -> list[TrialSummary]:
        """Extract TrialSummary from each trace."""
        summaries = []
        for spec, trace in zip(variants, traces):
            ds = trace.dynamics_summary
            sr = trace.simulation_result
            summaries.append(TrialSummary(
                variant_id=spec.variant_id,
                architecture_id=trace.architecture_id,
                best_score=float(sr.get("best_score", 0.0)),
                mean_score=float(ds.get("mean_score", 0.0)),
                final_convergence=float(ds.get("final_convergence", 0.0)),
                trajectory_drift=float(ds.get("trajectory_warnings", 0)),
                goodhart_total=int(ds.get("goodhart_total", 0)),
                halt_reason=str(sr.get("halt_reason", "")),
                total_cycles=int(sr.get("total_cycles", 0)),
                best_candidate=str(sr.get("best_candidate", ""))[:120],
            ))
        return summaries

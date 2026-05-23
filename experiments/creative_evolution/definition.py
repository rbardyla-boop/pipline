"""Formal ExperimentDefinition for the Creative Concept Evolution experiment.

This is Experiment #1 in the UAF ledger — the existing pipeline formalized
as a first-class, reproducible experiment binding.

Usage (UAF_KERNEL=true mode):
    from experiments.creative_evolution.definition import make_creative_evolution_experiment
    defn = make_creative_evolution_experiment(domain="gaming", seeds=["seed_a", "seed_b"])
    trace = ExperimentRunner().execute(defn)
    ExperimentLedger().record(trace)
"""

from __future__ import annotations

import os
from typing import Any

from uaf.experiments.definition import ExperimentDefinition
from uaf.kernel.invariants import InvariantSet


def make_creative_evolution_experiment(
    domain: str,
    seeds: list[str],
    config_overrides: dict[str, Any] | None = None,
) -> ExperimentDefinition:
    """Build an ExperimentDefinition for the creative concept evolution pipeline.

    This wires together all five adapters (claude_novelty, archive_memory,
    langgraph_planner, phoenix_verification, local_runtime) into a single
    runnable definition.

    Args:
        domain:           e.g. "gaming", "film", "saas"
        seeds:            Initial concept seeds (from YAML seed file)
        config_overrides: Optional overrides for generations, variants_per_gen, etc.

    Returns:
        A fully-configured ExperimentDefinition ready for ExperimentRunner.execute().
    """
    from engine import NoveltySearchEngine
    from concept_rater import ConceptRater
    from zeitgeist import ZeitgeistInjector

    from architectures.claude_novelty.adapter import ClaudeNoveltyCognition
    from experiments.creative_evolution.memory_adapter import ArchiveMemory
    from experiments.creative_evolution.planner_adapter import LangGraphPlanner
    from experiments.creative_evolution.verification_adapter import PhoenixVerification
    from experiments.creative_evolution.runtime_adapter import LocalRuntime

    # Shared engine instance — both cognition and memory use the same archive
    engine = NoveltySearchEngine()

    config = {
        "domain": domain,
        "seeds": seeds,
        "generations": int(os.getenv("GENERATIONS", "10")),
        "variants_per_gen": int(os.getenv("VARIANTS_PER_GEN", "6")),
        "max_loops": int(os.getenv("MAX_IMPROVEMENT_LOOPS", "4")),
        "plateau_delta": float(os.getenv("PLATEAU_DELTA", "0.10")),
        "v5_simulator": os.getenv("V5_SIMULATOR", "false").lower() == "true",
        "ephemeral_gate": os.getenv("EPHEMERAL_GATE", "false").lower() == "true",
    }
    if config_overrides:
        config.update(config_overrides)

    return ExperimentDefinition(
        experiment_id="creative_evolution_v1",
        architecture=ClaudeNoveltyCognition(engine),
        memory=ArchiveMemory(engine),
        planner=LangGraphPlanner(
            max_loops=config["max_loops"],
            plateau_delta=config["plateau_delta"],
        ),
        verification=PhoenixVerification(
            rater=ConceptRater(),
            engine=engine,
            run_sandbox=True,
        ),
        runtime=LocalRuntime(zeitgeist=ZeitgeistInjector()),
        invariants=InvariantSet.default(),
        config=config,
    )

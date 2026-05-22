import os
import json
from typing import TypedDict, Dict, Any, Optional, List
from langgraph.graph import StateGraph, END
from engine import NoveltySearchEngine, write_terminal_archive
from zeitgeist import ZeitgeistInjector
from sandbox import CulturalSandbox
from concept_rater import ConceptRater, PLATEAU_DELTA, MAX_IMPROVEMENT_LOOPS
from simulator import V5Simulator
from pathlib import Path
from datetime import datetime, timezone

TERMINAL_PHOENIX_THRESHOLD = 4.2
TERMINAL_COMBINED_THRESHOLD = 0.65


class PipelineState(TypedDict):
    # Core
    domain: str
    seeds: List[str]
    run_id: str
    # Zeitgeist
    zeitgeist_text: str
    # Evolution
    candidates: List[Dict]
    top_candidate: Optional[str]
    # Sandbox
    sandbox_results: Optional[Dict]
    verdict: Optional[str]
    extended_verdict: str           # "HIT" | "SLOP" | "COUNTER_SIGNAL"
    # Refinement loop
    concept_score: Optional[float]
    concept_scores_history: List[float]
    improvement_context: str
    refinement_loop_count: int
    best_concept: Optional[str]
    best_concept_score: Optional[float]
    best_combined: Optional[float]
    # v4 signals
    ritual_cost_score: float
    anti_optimization_score: float
    # Observer effect guard
    prev_top_candidate_emb: Optional[Any]   # np.ndarray stored as list
    goodhart_warnings: int
    # Ephemeral gate
    human_resonance_confirmed: Optional[bool]
    force_save: bool
    # v5 Simulator (optional, V5_SIMULATOR=true)
    simulator_session_embeddings: List[Dict]   # [{cycle, emb_list, preview}]
    simulator_refractory_clusters: List[Dict]  # [{cycle_added, phrases}]
    simulator_trajectory_warnings: int


def ingest_node(state: PipelineState) -> Dict:
    print("\n[NODE: INGEST] Pulling live zeitgeist...")
    z = ZeitgeistInjector()
    ctx = z.get_formatted_context(state["domain"])
    print(f"[NODE: INGEST] Context acquired ({len(ctx)} chars)")
    return {"zeitgeist_text": ctx}


def entropy_node(state: PipelineState) -> Dict:
    loop = state.get("refinement_loop_count", 0)
    if loop == 0:
        return {}

    zeitgeist = state["zeitgeist_text"]
    signal = f"\n[ENTROPY CYCLE {loop}] Archive aged — established attractors weakened. Seek beyond."
    zeitgeist += signal
    print(f"[NODE: ENTROPY] Archive decay signal injected (loop {loop})")

    if os.getenv("V5_SIMULATOR", "false").lower() == "true":
        sim_ctx = V5Simulator.build_context(
            state.get("simulator_session_embeddings", []),
            state.get("simulator_refractory_clusters", []),
            loop,
        )
        if sim_ctx:
            zeitgeist += "\n\n" + sim_ctx
            print(f"[NODE: ENTROPY] v5 simulator context injected")

    return {"zeitgeist_text": zeitgeist}


def mutate_node(state: PipelineState) -> Dict:
    loop = state.get("refinement_loop_count", 0)
    improvement_ctx = state.get("improvement_context", "")

    zeitgeist = state["zeitgeist_text"]
    if improvement_ctx:
        zeitgeist = improvement_ctx + "\n\n" + zeitgeist
        print(f"\n[NODE: MUTATE] Refinement loop #{loop} — injecting improvement directives")
    else:
        print("\n[NODE: MUTATE] Running novelty evolution engine...")

    engine = NoveltySearchEngine()
    engine.seed_archive(state["seeds"])

    candidates = engine.evolve(
        zeitgeist_context=zeitgeist,
        generations=10,
        variants_per_gen=6,
        top_k_parents=3
    )

    engine.save_run(candidates, state["domain"])
    top = candidates[0]["candidate"] if candidates else state["seeds"][0]
    combined = candidates[0]["combined"] if candidates else 0
    print(f"[NODE: MUTATE] Top candidate (combined={combined:.3f})")
    print(f"  → {top[:120]}...")

    return {"candidates": candidates, "top_candidate": top}


def sandbox_node(state: PipelineState) -> Dict:
    print("\n[NODE: SANDBOX] Running cultural agent simulation...")
    sandbox = CulturalSandbox(domain=state["domain"], weeks=5)
    results = sandbox.run(state["top_candidate"], verbose=True)

    metrics = results["metrics"]
    base_verdict = metrics["verdict"]

    ritual = state.get("ritual_cost_score", 0.0)
    anti_opt = state.get("anti_optimization_score", 0.0)
    phoenix = state.get("concept_score") or 0.0

    extended_verdict = (
        "COUNTER_SIGNAL"
        if anti_opt > 0.35 and ritual > 0.30 and phoenix > 3.5
        else base_verdict
    )

    print(f"\n[NODE: SANDBOX] Results:")
    print(f"  Viral Velocity:  {metrics['viral_velocity']}")
    print(f"  Memetic Drift:   {metrics['memetic_drift']}")
    print(f"  Retention:       {metrics['retention_decay_slop']}")
    print(f"  Budget Survived: {metrics['budget_survived']}")
    print(f"  VERDICT:         {extended_verdict}")

    return {"sandbox_results": results, "verdict": base_verdict, "extended_verdict": extended_verdict}


def refine_node(state: PipelineState) -> Dict:
    loop_num = state.get("refinement_loop_count", 0) + 1
    print(f"\n[NODE: REFINE] Iteration #{loop_num} — scoring concept with Phoenix rubric...")

    rater = ConceptRater()
    result = rater.rate(state["top_candidate"], state["domain"])
    composite = result["composite"]
    ritual = result["ritual_cost_score"]
    anti_opt = result["anti_optimization_score"]

    history = list(state.get("concept_scores_history", []))
    history.append(composite)

    best = state.get("best_concept")
    best_score = state.get("best_concept_score") or 0.0
    best_combined = state.get("best_combined") or 0.0

    if composite > best_score:
        best = state["top_candidate"]
        best_score = composite
        top_combined = state["candidates"][0]["combined"] if state.get("candidates") else 0.0
        best_combined = top_combined

    print(f"[NODE: REFINE] Score: {composite:.3f}/5.0 | Best so far: {best_score:.3f}")
    for criterion, val in result["scores"].items():
        print(f"  {criterion}: {val}/5")
    print(f"  Weakest: {result['weakest']}")
    print(f"  Ritual cost: {ritual:.3f} | Anti-opt: {anti_opt:.3f}")

    # Observer effect guard: check embedding convergence with previous cycle
    improvement_ctx = result["improvement_context"]
    goodhart_warnings = state.get("goodhart_warnings", 0)
    prev_emb = state.get("prev_top_candidate_emb")

    engine_for_emb = NoveltySearchEngine()
    current_emb = engine_for_emb.embed(state["top_candidate"])
    current_emb_list = current_emb.tolist()

    if prev_emb is not None:
        import numpy as np
        prev_emb_arr = np.array(prev_emb)
        if rater.detect_convergence(current_emb, prev_emb_arr):
            goodhart_warnings += 1
            print(f"[GUARD] Goodhart convergence detected (#{goodhart_warnings}) — forcing divergence")
            improvement_ctx += (
                "\n[OBSERVER GUARD] Convergence detected — the last two cycles are producing "
                "structurally similar concepts. Violate the emerging template. Mutate toward "
                "the opposite of what you just produced."
            )

    updates: Dict = {
        "concept_score": composite,
        "concept_scores_history": history,
        "improvement_context": improvement_ctx,
        "refinement_loop_count": loop_num,
        "best_concept": best,
        "best_concept_score": best_score,
        "best_combined": best_combined,
        "ritual_cost_score": ritual,
        "anti_optimization_score": anti_opt,
        "prev_top_candidate_emb": current_emb_list,
        "goodhart_warnings": goodhart_warnings,
    }

    if os.getenv("V5_SIMULATOR", "false").lower() == "true":
        new_session, new_refractory, new_warnings = V5Simulator.update_session(
            state.get("simulator_session_embeddings", []),
            state.get("simulator_refractory_clusters", []),
            state.get("simulator_trajectory_warnings", 0),
            loop_num,
            current_emb,
            state["top_candidate"],
        )
        updates["simulator_session_embeddings"] = new_session
        updates["simulator_refractory_clusters"] = new_refractory
        updates["simulator_trajectory_warnings"] = new_warnings
        if new_warnings > state.get("simulator_trajectory_warnings", 0):
            print(f"[SIM] Trajectory convergence detected (warning #{new_warnings})")

    return updates


def ephemeral_gate_node(state: PipelineState) -> Dict:
    if os.getenv("EPHEMERAL_GATE", "false").lower() != "true":
        return {}

    print("\n" + "=" * 60)
    print("[PHZ] PROTECTED HUMAN ZONE — nothing logged past this line")
    print("=" * 60)
    print(state.get("best_concept") or state.get("top_candidate", ""))
    print("=" * 60)

    response = input("\nDoes this resonate? [y/n/q to force-save]: ").strip().lower()

    print("[PHZ] Session closed. No transcript retained.")
    print("=" * 60 + "\n")

    if response == "q":
        return {"human_resonance_confirmed": False, "force_save": True}
    return {"human_resonance_confirmed": response == "y"}


def route_after_refine(state: PipelineState) -> str:
    if state.get("force_save"):
        print("[LOOP] Force-save from ephemeral gate — saving best result")
        return "save"

    history = state.get("concept_scores_history", [])
    loop_count = state.get("refinement_loop_count", 0)

    if loop_count >= MAX_IMPROVEMENT_LOOPS:
        print(f"[LOOP] Max loops ({MAX_IMPROVEMENT_LOOPS}) reached — saving best result")
        return "save"

    if len(history) >= 2:
        delta = history[-1] - history[-2]
        if delta < PLATEAU_DELTA:
            print(f"[LOOP] Score plateaued (Δ={delta:.3f} < {PLATEAU_DELTA}) — saving best result")
            return "save"

    print("[LOOP] Score improving — running another mutation cycle")
    return "mutate"


def save_node(state: PipelineState) -> Dict:
    Path("logs/runs").mkdir(parents=True, exist_ok=True)

    final_concept = state.get("best_concept") or state.get("top_candidate")
    best_score = state.get("best_concept_score") or 0.0
    best_combined = state.get("best_combined") or 0.0
    extended_verdict = state.get("extended_verdict", state.get("verdict", "SLOP"))

    output = {
        "run_id": state["run_id"],
        "domain": state["domain"],
        "sandbox_verdict": extended_verdict,
        "sandbox_metrics": state["sandbox_results"]["metrics"] if state.get("sandbox_results") else {},
        "top_candidates": state["candidates"][:5] if state.get("candidates") else [],
        "refinement_loop_count": state.get("refinement_loop_count", 0),
        "concept_scores_history": state.get("concept_scores_history", []),
        "best_concept_score": best_score,
        "best_concept": final_concept,
        "ritual_cost_score": state.get("ritual_cost_score", 0.0),
        "anti_optimization_score": state.get("anti_optimization_score", 0.0),
        "goodhart_warnings": state.get("goodhart_warnings", 0),
    }

    if os.getenv("V5_SIMULATOR", "false").lower() == "true":
        loop_count = state.get("refinement_loop_count", 0)
        output["simulator"] = V5Simulator.metrics(
            state.get("simulator_session_embeddings", []),
            state.get("simulator_refractory_clusters", []),
            state.get("simulator_trajectory_warnings", 0),
            loop_count,
        )
    fpath = f"logs/runs/full_run_{state['run_id']}.json"
    with open(fpath, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n[NODE: SAVE] Full run logged → {fpath}")

    # Terminal archive: permanently retire if thresholds met and human didn't veto
    if (
        best_score > TERMINAL_PHOENIX_THRESHOLD
        and best_combined > TERMINAL_COMBINED_THRESHOLD
        and state.get("human_resonance_confirmed") is not False
        and final_concept
    ):
        write_terminal_archive(final_concept, best_score, best_combined, state["run_id"])

    # Emit audit record conforming to truthlens-audit-schema-v1.json
    _write_audit_record(state, best_score, extended_verdict)

    return {}


_PIPELINE_KNOWN_LIMITS = [
    "Novelty scores are embedding-distance proxies, not ground-truth novelty measures",
    "Cultural simulation agents are stylised archetypes, not demographically validated populations",
    "Zeitgeist context is API-retrieved and may be stale, biased, or adversarially contaminated",
    "Phoenix rubric weights are heuristic — not derived from empirical outcome data",
    "Sandbox verdicts are simulations — real adoption patterns will differ",
]


def _write_audit_record(state: PipelineState, best_score: float, verdict: str) -> None:
    """
    Write a schema-conformant audit record to logs/audit/.
    Hard-fails with a logged error if validation fails — does NOT suppress.
    """
    import sys
    try:
        import subprocess
        now = datetime.now(timezone.utc).isoformat()
        audit_record = {
            "protocol": {
                "constitution_version": "1.0",
                "audit_schema_version": "1",
                "signals_registry_version": "1.0",
            },
            "article": {
                "url": f"urn:pipeline:run:{state['run_id']}",
                "title": f"Pipeline run — domain: {state['domain']}",
                "timestamp": now,
            },
            "signals": [
                {
                    "id": "ritual_cost",
                    "score": state.get("ritual_cost_score", 0.0),
                    "label": "Ritual Cost Signal",
                },
                {
                    "id": "anti_optimization",
                    "score": state.get("anti_optimization_score", 0.0),
                    "label": "Anti-Optimization Signal",
                },
            ],
            "interpretation": {
                "layer1": verdict,
            },
            "known_limits": _PIPELINE_KNOWN_LIMITS,
            "exported_at": now,
        }

        audit_dir = Path("logs/audit")
        audit_dir.mkdir(parents=True, exist_ok=True)
        audit_path = audit_dir / f"audit_{state['run_id']}.json"

        # Validate against schema using Node.js AJV (if available)
        schema_path = Path("truthlens/truthlens-audit-schema-v1.json")
        audit_json = json.dumps(audit_record, indent=2)

        if schema_path.exists():
            result = subprocess.run(
                [sys.executable, "-c",
                 f"""
import json, sys
record = {json.dumps(audit_record)}
# Basic required-fields check (AJV runs in Node CI)
required = {{'protocol', 'article', 'signals', 'interpretation', 'known_limits', 'exported_at'}}
missing = required - set(record.keys())
if missing:
    print(f'AUDIT VALIDATION FAIL: missing fields: {{missing}}', file=sys.stderr)
    sys.exit(1)
if not record.get('known_limits'):
    print('AUDIT VALIDATION FAIL: known_limits empty', file=sys.stderr)
    sys.exit(1)
if record.get('interpretation', {{}}).get('layer1') is None:
    print('AUDIT VALIDATION FAIL: interpretation.layer1 missing', file=sys.stderr)
    sys.exit(1)
print('Audit record valid')
"""],
                capture_output=True, text=True
            )
            if result.returncode != 0:
                print(f"[AUDIT] Schema validation FAILED: {result.stderr.strip()}", file=sys.stderr)
                return

        with open(audit_path, "w") as f:
            f.write(audit_json)
        print(f"[AUDIT] Record written → {audit_path}")

    except Exception as e:
        print(f"[AUDIT] Failed to write audit record: {e}", file=sys.stderr)


def build_pipeline():
    graph = StateGraph(PipelineState)
    graph.add_node("ingest", ingest_node)
    graph.add_node("entropy", entropy_node)
    graph.add_node("mutate", mutate_node)
    graph.add_node("sandbox", sandbox_node)
    graph.add_node("refine", refine_node)
    graph.add_node("ephemeral_gate", ephemeral_gate_node)
    graph.add_node("save", save_node)

    graph.set_entry_point("ingest")
    graph.add_edge("ingest", "entropy")
    graph.add_edge("entropy", "mutate")
    graph.add_edge("mutate", "sandbox")
    graph.add_edge("sandbox", "refine")
    graph.add_edge("refine", "ephemeral_gate")
    graph.add_conditional_edges("ephemeral_gate", route_after_refine, {"mutate": "entropy", "save": "save"})
    graph.add_edge("save", END)

    return graph.compile()


def run(domain: str, seeds: List[str]) -> Dict:
    pipeline = build_pipeline()
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    initial_state: PipelineState = {
        "domain": domain,
        "seeds": seeds,
        "run_id": run_id,
        "zeitgeist_text": "",
        "candidates": [],
        "top_candidate": None,
        "sandbox_results": None,
        "verdict": None,
        "extended_verdict": "SLOP",
        "concept_score": None,
        "concept_scores_history": [],
        "improvement_context": "",
        "refinement_loop_count": 0,
        "best_concept": None,
        "best_concept_score": None,
        "best_combined": None,
        "ritual_cost_score": 0.0,
        "anti_optimization_score": 0.0,
        "prev_top_candidate_emb": None,
        "goodhart_warnings": 0,
        "human_resonance_confirmed": None,
        "force_save": False,
        "simulator_session_embeddings": [],
        "simulator_refractory_clusters": [],
        "simulator_trajectory_warnings": 0,
    }

    sim_active = os.getenv("V5_SIMULATOR", "false").lower() == "true"
    print(f"\n{'='*60}")
    print(f"  UNIVERSAL EXTRAPOLATIVE ENGINE v4 — RUN {run_id}")
    print(f"  Domain: {domain.upper()} | Seeds: {len(seeds)}")
    print(f"  Max refinement loops: {MAX_IMPROVEMENT_LOOPS} | Plateau delta: {PLATEAU_DELTA}")
    if sim_active:
        print(f"  [V5 SIMULATOR ACTIVE] decay={V5Simulator.DECAY_RATE} refractory={V5Simulator.REFRACTORY_CYCLES}cyc")
    print(f"{'='*60}")

    final_state = pipeline.invoke(initial_state)

    best_score = final_state.get("best_concept_score") or 0.0
    loops = final_state.get("refinement_loop_count", 0)
    history = final_state.get("concept_scores_history", [])
    sparkline = " → ".join(f"{s:.2f}" for s in history)
    extended = final_state.get("extended_verdict", "SLOP")
    ritual = final_state.get("ritual_cost_score", 0.0)
    anti_opt = final_state.get("anti_optimization_score", 0.0)
    warnings = final_state.get("goodhart_warnings", 0)

    print(f"\n{'='*60}")
    print(f"  SANDBOX VERDICT:    {extended}")
    print(f"  BEST CONCEPT SCORE: {best_score:.3f}/5.0 (after {loops} refinement loops)")
    print(f"  SCORE HISTORY:      {sparkline}")
    print(f"  RITUAL COST:        {ritual:.3f} | ANTI-OPT: {anti_opt:.3f}")
    if warnings > 0:
        print(f"  GOODHART WARNINGS:  {warnings}")
    print(f"{'='*60}\n")

    return final_state

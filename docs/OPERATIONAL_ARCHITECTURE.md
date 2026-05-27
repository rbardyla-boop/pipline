# Operational Architecture — UEE v4 / UAF

Pure engineering reference. No philosophy. Updated every time the graph changes.

> **Default execution path (as of Phase 6 cutover):** UAF kernel (`UAF_KERNEL=true`).  
> Legacy LangGraph pipeline (below) is still active when `UAF_KERNEL=false`.  
> Both paths share the same seed files, environment variables, and output format.

---

## UAF Execution Path (default, `UAF_KERNEL=true`)

```
main.py → _run_uaf()
  └─ make_creative_evolution_experiment()
       └─ ExperimentRunner.execute(defn)
            └─ SimulationKernel.run(ctx)
                 loop: EXECUTE → VERIFY → COMMIT → COMPRESS → STABILIZE → PLAN → HALT?
            └─ DynamicsRecorder.record() per cycle
  └─ ExperimentLedger.record(trace)
  └─ logs/runs/full_run_{trace.run_id}.json
```

**State machine (actual):** `INIT → EXECUTE → VERIFY → COMMIT → COMPRESS → STABILIZE → [HALT | EXECUTE]`  
Note: `OBSERVE` and `PLAN` states exist in the enum but are not executed — see TD-004 in `docs/TECH_DEBT.md`.

---

## Graph Topology

```
ingest → entropy → mutate → sandbox → refine → ephemeral_gate → [route] → save
                                                                     ↓ mutate
                                                               entropy (loop)
```

**Entry:** `ingest`  
**Exit:** `save → END`  
**Loop:** `ephemeral_gate → route_after_refine → entropy → mutate` (when score improving)

---

## Nodes

| Node | Function | Key Outputs |
|------|----------|-------------|
| `ingest` | `ingest_node()` | `zeitgeist_text` |
| `entropy` | `entropy_node()` | `zeitgeist_text` (appends decay signal on loop > 0) |
| `mutate` | `mutate_node()` | `candidates`, `top_candidate` |
| `sandbox` | `sandbox_node()` | `sandbox_results`, `verdict`, `extended_verdict` |
| `refine` | `refine_node()` | `concept_score`, `concept_scores_history`, `improvement_context`, `ritual_cost_score`, `anti_optimization_score`, `prev_top_candidate_emb`, `goodhart_warnings` |
| `ephemeral_gate` | `ephemeral_gate_node()` | `human_resonance_confirmed`, `force_save` (only when `EPHEMERAL_GATE=true`) |
| `save` | `save_node()` | writes `logs/runs/full_run_{run_id}.json`, optionally writes `logs/terminal_archive.json` |

---

## Routing

`route_after_refine(state) -> "mutate" | "save"`

Priority order:
1. `force_save=True` → "save"
2. `refinement_loop_count >= MAX_IMPROVEMENT_LOOPS` (4) → "save"
3. `len(history) >= 2 AND delta < PLATEAU_DELTA` (0.10) → "save"
4. else → "mutate"

When routing "mutate", graph re-enters at `entropy` (not `mutate` directly).

---

## Verdict Types

| Verdict | Condition |
|---------|-----------|
| `HIT` | viral_velocity > 4.0 AND memetic_drift > 0.4 AND retention > 0.3 |
| `SLOP` | any HIT condition fails |
| `COUNTER_SIGNAL` | anti_opt > 0.35 AND ritual_cost > 0.30 AND phoenix > 3.5 (overrides sandbox verdict) |

---

## Score Signals

### Phoenix Rubric (composite: weighted sum, range 0–5)

| Criterion | Weight | Meaning |
|-----------|--------|---------|
| hook_strength | 0.30 | Stops conversation mid-scroll |
| specificity | 0.25 | Concrete enough to prototype |
| emotional_activation | 0.20 | Hits a 2026 cultural nerve |
| action_clarity | 0.15 | PM knows what to build next |
| platform_fit | 0.10 | Fills an existing gap |

### v4 Orthogonal Signals (NOT in composite)

| Signal | Source | Meaning |
|--------|--------|---------|
| `ritual_cost_score` | `FRICTION_PATTERNS` regex | Friction density (physical, embodied, irreversible) |
| `anti_optimization_score` | `ANTI_OPT_PATTERNS` regex | Explicit rejection of automation/dashboards |
| `goodhart_warnings` | embedding convergence | Count of cycles where consecutive candidates converged |

### v5 Simulator State (optional, `V5_SIMULATOR=true`)

| Field | Meaning |
|-------|---------|
| `simulator_session_embeddings` | Per-cycle top-candidate embeddings as lists [{cycle, emb_list, preview}] |
| `simulator_refractory_clusters` | Phrase clusters locked out for N cycles [{cycle_added, phrases}] |
| `simulator_trajectory_warnings` | Count of cycles where session-wide avg pairwise distance < 0.35 |

Context injected into `zeitgeist_text` via `entropy_node()` on loop > 0:
- `[V5-DECAY]` — Prior cycle outputs weighted by age; mutation directed away proportionally
- `[V5-REFRACTORY]` — Locked-out phrase clusters from recent cycles
- `[V5-REPULSION]` — Max divergence directive when session trajectory converges

These signals inform human judgment. They must not enter the optimization loop.

---

## Memory Systems

### Rolling Archive (per-run, in-memory)

`NoveltySearchEngine.archive: List[Dict]`
- Max 500 entries (`ARCHIVE_MAX` env)
- Sorted by novelty (descending) on pruning
- Entropy decay applied at start of each generation after first: `novelty *= max(0.1, 1 - age * ENTROPY_DECAY_RATE)`
- `ENTROPY_DECAY_RATE` default: 0.05

### Terminal Archive (persistent, cross-run)

`logs/terminal_archive.json`
- Concepts with Phoenix > 4.2 AND combined > 0.65 AND no human veto
- Format: `{concept_hash, concept_preview, phoenix_score, combined, run_id, retired_at}`
- `concept_hash`: sha256[:16] of concept text
- **Excluded from parent selection in all future runs**
- Never re-indexed, never re-activated

---

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `ANTHROPIC_API_KEY` | required | Claude API |
| `TAVILY_API_KEY` | optional | Live zeitgeist fetching |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | SentenceTransformer model |
| `NOVELTY_THRESHOLD` | 0.68 | Minimum novelty to archive a variant |
| `ARCHIVE_MAX` | 500 | Max rolling archive size |
| `ENTROPY_DECAY_RATE` | 0.05 | Per-generation novelty decay rate |
| `TERMINAL_ARCHIVE_PATH` | `logs/terminal_archive.json` | Terminal archive location |
| `EPHEMERAL_GATE` | `false` | Enable human PHZ checkpoint |
| `V5_SIMULATOR` | `false` | Enable v5 prompt-level simulator |
| `V5_DECAY_RATE` | `0.05` | Per-cycle context decay rate for simulator |
| `V5_REFRACTORY_CYCLES` | `2` | Cycles a phrase cluster stays locked out |

---

## File Outputs

| File | Written by | Contents |
|------|-----------|---------|
| `logs/runs/{domain}_{timestamp}.json` | `engine.save_run()` | Per-generation top-3 candidates |
| `logs/runs/full_run_{run_id}.json` | `save_node()` | Complete run: best concept, score history, all v4 signals |
| `logs/terminal_archive.json` | `write_terminal_archive()` | Permanently retired concepts |

---

## Constants

| Constant | Value | File |
|----------|-------|------|
| `PLATEAU_DELTA` | 0.10 | `concept_rater.py` |
| `MAX_IMPROVEMENT_LOOPS` | 4 | `concept_rater.py` |
| `CONVERGENCE_THRESHOLD` | 0.85 | `concept_rater.py` |
| `TERMINAL_PHOENIX_THRESHOLD` | 4.2 | `orchestrator.py` |
| `TERMINAL_COMBINED_THRESHOLD` | 0.65 | `orchestrator.py` |

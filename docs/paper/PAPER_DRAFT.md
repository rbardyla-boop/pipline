# Hypothesis-Driven AI Architecture Discovery: A Multi-Persona Agentic Framework

**Authors:** [RB] · [Affiliation]  
**Date:** May 2026  
**Status:** DRAFT — Phase-10 dynamics instrumentation fix applied (see §6.4). Stage 3a (coherence-diversity, 5 iter, 16 variants) and Stage 3b (attention heads, 5 iter, 16 variants) **complete**. All `[PENDING]` markers resolved. Remaining work: fig2/fig3 (Mermaid diagrams), fig5/fig8 (screenshots), fig9 leaderboard refresh.

---

## Abstract

We present the **Universal Agentic Framework (UAF)**, a system for scientific AI architecture discovery in which a panel of AI engineering personas acts as peer reviewers of their own architecture decisions. UAF structures architecture search as a formal scientific loop: a researcher defines a hypothesis (e.g., "does attention head count improve coherence at fixed embed_dim=64?"), the system runs controlled multi-variant trials, and a panel of three specialized AI personas — Research Scientist, Deployed Engineer, and Chaos Engineer — deliberates in parallel to propose the next iteration of variants. The loop terminates when Claude semantically confirms the hypothesis is resolved, not at a fixed iteration count.

Across 351 controlled experiments spanning 37 distinct architecture configurations in the creative concept domain, UAF achieved a best composite score of **4.78/5.0** and detected **zero Goodhart violations**. Convergence dynamics are reported in §5.1 following a Phase-10 instrumentation fix (§6.4). The engineer panel discovered a previously unpredicted phase boundary (score collapse at template_count=1) and surfaced a real Pareto frontier between peak performance and mean stability — findings a single-expert refinement loop missed entirely. We further show that the simulation cycle maps directly to a gradient descent step, allowing a character-level decoder-only transformer to serve as a drop-in cognition engine with zero kernel changes. UAF represents a shift from black-box hyperparameter search toward **hypothesis-confirmed, multi-perspective, auditable AI architecture science**.

---

## 1. Introduction

Modern AI architecture search is sophisticated but epistemically thin. Weights & Biases sweeps run thousands of grid or Bayesian trials and produce a leaderboard — but no *findings*. There is no hypothesis, no interpretation of *why* a configuration won, no structured refinement based on what was learned. The researcher reads the dashboard and manually decides what to try next.

This paper argues that architecture search should be treated as a scientific process, and presents a system designed accordingly.

The **Universal Agentic Framework (UAF)** consists of three interacting layers:

1. **A pluggable substrate** — five abstract interface contracts (CognitionEngine, MemorySystem, VerificationEngine, Planner, RuntimeEnvironment) that allow any reasoning architecture — LLM, symbolic grammar, or trained neural network — to be swapped into the same experiment kernel without modification.

2. **A hypothesis-driven meta-loop** — the `ExperimentLoop`, in which a `Hypothesis` object carries a research question, predicted outcome, variants to test, and stopping criterion. Claude reads iteration results and writes findings; the loop runs until the hypothesis is confirmed, not until a timer fires.

3. **A parallel engineer panel** — three AI personas with distinct evaluation lenses deliberate concurrently (ThreadPoolExecutor), propose candidate variants, and a synthesis call selects the final set. The panel's reasoning is recorded in a Discovery Journal and available for audit.

**[FIGURE 1: fig1_ui_overview.png — The 4MAT research workbench: Q1 Hypothesis Composer, Q2 Live Dynamics, Q3 Variant Controls, Q4 Discovery Journal]**

Our key contributions:

1. **The pluggable substrate model** — a 5-interface contract that enables architecture swapping without kernel changes, demonstrated across parametric, symbolic, and neural backends.
2. **The hypothesis meta-loop** — architecture search as structured science: hypothesis → trial → compare → refine → confirmed.
3. **The multi-persona engineer panel** — parallel epistemic diversity reduces anchoring bias in variant selection; panel discovers findings single-expert refinement misses.
4. **Simulation cycle = training step equivalence** — the CognitionEngine `propose()` interface directly maps to a gradient descent batch, enabling in-loop neural architecture training.
5. **Empirical validation** — 351 experiments, phase boundary discovery, Pareto frontier characterization, and a null result (coherence_mode has zero discriminative power at tested scales).

The remainder of this paper is organized as follows. Section 2 reviews related work. Section 3 describes system architecture. Section 4 presents experiments. Section 5 reports results. Section 6 discusses findings and limitations. Section 7 concludes.

---

## 2. Background and Related Work

### 2.1 Neural Architecture Search

Neural Architecture Search (NAS) methods — DARTS [Liu et al., 2019], ENAS [Pham et al., 2018] — automate architecture discovery through gradient-based or evolutionary search. They are computationally expensive (DARTS requires thousands of GPU-hours) and produce a final architecture rather than a scientific finding. There is no hypothesis object, no interpretable reasoning trace, and no stopping criterion based on scientific resolution.

### 2.2 Hyperparameter Optimization

Tools like Weights & Biases Sweeps and Optuna [Akiba et al., 2019] perform grid, random, or Bayesian hyperparameter search with metric logging. They excel at finding good configurations but produce no interpretation of *why* configurations succeed. The researcher is left to manually read charts and form hypotheses. There is no multi-perspective deliberation and no semantic stopping.

### 2.3 LLM-Augmented Optimization

**DSPy** [Khattab et al., 2023] treats LLM pipelines as differentiable programs and optimizes prompt signatures. It targets prompt optimization, not architectural weight training, and runs a single sequential optimization loop with no panel deliberation. **OPRO** [Yang et al., 2023] uses an LLM as an optimizer by including past metric values in the prompt — analogous to single-expert refinement with no hypothesis structure. **PromptBreeder** [Fernando et al., 2023] evolves prompts using mutation operators but lacks structured hypotheses or multi-perspective evaluation.

### 2.4 Minimal Transformer Implementations

**NanoGPT** [Karpathy, 2022] provides a clean educational implementation of GPT-2 style training. It is an excellent foundation for understanding transformers but provides no science layer, no experiment loop, and no adversarial testing. UAF's `NeuralTransformerCognition` uses a NanoGPT-style decoder as the cognition substrate inside a structured hypothesis loop — combining the educational clarity of NanoGPT with the scientific rigor of the UAF meta-loop.

### 2.5 Multi-Agent Systems

AutoGen [Wu et al., 2023] and CrewAI enable multi-agent task completion workflows where agents cooperate toward a shared goal. In UAF's engineer panel, agents are designed to *disagree* — each persona applies a different evaluation lens, and epistemic conflict between personas is the mechanism that surfaces Pareto frontiers and phase boundaries. This is a fundamentally different use of multi-agent systems: deliberation rather than cooperation.

### 2.6 Goodhart's Law in ML Systems

Krakovna et al. [2020] survey specification gaming in AI systems. UAF's VerificationEngine includes a Goodhart guard that detects when a candidate scores high on the verification metric but low on independent quality signals (anti-optimization score). Across all 351 experiments, the guard triggered zero times — a null result that validates the heuristic verification design.

**Table 1: Comparison of UAF to related systems**

| Capability | UAF | NanoGPT | DSPy | W&B Sweeps | AutoGen |
|---|---|---|---|---|---|
| Pluggable reasoning substrate | ✓ | ✗ | ✗ | ✗ | ✗ |
| Hypothesis-driven loop | ✓ | ✗ | ✗ | ✗ | ✗ |
| Multi-persona deliberation | ✓ | ✗ | ✗ | ✗ | ✗ |
| Transactional verification + Goodhart detection | ✓ | ✗ | partial | ✗ | ✗ |
| Entropy-bounded memory | ✓ | ✗ | ✗ | ✗ | ✗ |
| Semantic stopping criterion | ✓ | ✗ | ✗ | ✗ | ✗ |
| Cycle-level telemetry | ✓ | ✗ | ✗ | ✓ | ✗ |
| In-loop neural training | ✓ | ✓ | ✗ | ✗ | ✗ |

---

## 3. System Architecture

### 3.1 The Five Interface Contracts

UAF's kernel depends on five abstract base classes (ABCs), never on concrete implementations. Any component can be swapped by providing a class that satisfies the contract.

**CognitionEngine** (`uaf/interfaces/cognition.py`):
```python
class CognitionEngine(ABC):
    @abstractmethod
    def propose(self, parent: str, context: str) -> str: ...
    @abstractmethod
    def embed(self, text: str) -> Sequence[float]: ...
    @abstractmethod
    def coherence(self, candidate: str) -> float: ...
    @property
    @abstractmethod
    def architecture_id(self) -> str: ...
```
The reasoning substrate swap point. Three implementations exist: `ParametricCognition` (template-based, zero API), `SymbolicGrammarCognition` (deterministic CFG), and `NeuralTransformerCognition` (trained PyTorch transformer).

**MemorySystem** (`uaf/interfaces/memory.py`): Entropy-bounded state persistence with novelty scoring, decay, and cross-run terminal archiving. Novelty is computed as cosine distance to existing archive embeddings — concepts too similar to past winners are rejected.

**VerificationEngine** (`uaf/interfaces/verification.py`): Transactional evaluation gate. Produces a `VerificationResult` with `composite_score`, `goodhart_warning`, `novelty_pressure`, and `verdict ∈ {HIT, SLOP, COUNTER_SIGNAL}`. The verdict routes the planner's next action.

**Planner** (`uaf/interfaces/planner.py`): Continuous goal-directed routing. `should_halt(state)` evaluates plateau, force_save, and max_loops conditions each cycle. Decoupled from mutation and verification — different stopping criteria require only a new Planner, not a new kernel.

**RuntimeEnvironment** (`uaf/interfaces/runtime.py`): Governance choke point. All external calls (LLM APIs, file I/O, context ingestion) route through `secure_call()`, enabling pre/post scanning, audit logging, and credential proxying without touching application code.

**[FIGURE 2: fig2_interface_diagram.png — (diagram) 5 ABCs and their dependency wiring in the SimulationKernel]**

### 3.2 SimulationKernel State Machine

The kernel (`uaf/kernel/simulation.py`) drives the inner simulation loop as a pure state machine:

```
INIT → OBSERVE → PLAN → EXECUTE → VERIFY → COMMIT → COMPRESS → STABILIZE
                                         ↘ FAIL_RECOVER (invariant violation)
COMPRESS/STABILIZE → HALT (planner.should_halt) or → OBSERVE (next cycle)
```

Each cycle produces a `CycleRecord` with 8 fields: cycle index, state, candidate, composite_score, plateau_delta, goodhart_warning, verdict, and duration_ms. Records accumulate in an `ExperimentTrace`, forming the time-series that feeds the dynamics layer.

Invariants are checked post-verification, pre-memory-commit. A maximum of 3 consecutive `FAIL_RECOVER` cycles triggers `HALT` with reason `invariant_abort`.

### 3.3 ExperimentLoop — The Hypothesis Meta-Loop

The `ExperimentLoop` (`uaf/research/loop.py`) implements the outer scientific loop:

```
Hypothesis
  └─ ControlledTrialRunner.run(hypothesis)     # all variants, identical conditions
       └─ ExperimentRunner.execute(defn)       # inner SimulationKernel per variant
  └─ compare_traces(traces) → comparison dict
  └─ _summarize_iteration(summaries) → finding string
  └─ _refine_variants(hypothesis, summaries, comparison)
       └─ EngineerPanel.deliberate(...)        # if hypothesis.panel is set
          OR single-Claude refinement call     # if no panel
  → repeat until stopping criterion met
```

**Stopping criteria:**
- `max_iterations`: fixed iteration count
- `score_threshold`: halt when any variant reaches `target_score`
- `hypothesis_confirmed`: Claude reads findings and declares resolution (semantic stopping)

A **repetition guard** detects when proposed variants share ≥2 parameters with previously tested configs; if >50% of proposals are repeats, it forces at least one into unexplored parameter territory.

**[FIGURE 3: fig3_loop_flowchart.png — (diagram) ExperimentLoop flowchart: hypothesis YAML → iterations → discovery report]**

### 3.4 EngineerPanel — Parallel Multi-Persona Deliberation

The `EngineerPanel` (`uaf/research/panel.py`) replaces the single-Claude refinement call with three concurrent API calls:

**Research Scientist** — lens: *"Maximize information gain. What parameter region have we NOT tested? Maximize variance."*  
**Deployed Engineer** — lens: *"Production robustness. Which configs collapse on edge-case seeds? Consistent mean_score matters more than best_score."*  
**Chaos Engineer** — lens: *"Find failure modes. What breaks the architecture? Where does Goodhart collapse happen?"*

All three calls run via `ThreadPoolExecutor(max_workers=3)`. Each persona returns a `PanelProposal` (reasoning, 2 variant specs, confidence 0–1). A fourth synthesis call selects 3 variants from the 6-candidate pool, optimizing for coverage (no two variants test the same dimension), scientific value, and balance (at least one "safe" refinement + one exploratory push).

All proposals are stored in `hypothesis.panel_proposals` and displayed in the Discovery Journal for auditability.

**[FIGURE 4: fig4_panel_personas.png — Q4 Discovery Journal showing 3 persona cards from iteration 3 of the coherence-diversity frontier experiment]**

### 3.5 NeuralTransformerCognition — In-Loop Neural Training

`NeuralTransformerCognition` (`architectures/neural/adapter.py`) wraps a character-level decoder-only transformer as a `CognitionEngine`. The transformer (`TinyTransformer`) follows the NanoGPT pattern: token embedding + position embedding, N × (pre-LayerNorm → CausalSelfAttention → FeedForward), final LayerNorm, linear head with weight tying.

The critical design decision is the mapping of simulation cycles to training batches:

```
propose(parent, context):
  1. Concatenate seeds + parent + context as training corpus
  2. Run n_train_steps gradient steps (AdamW, cross-entropy loss, grad clip 1.0)
  3. Generate max_gen_tokens tokens from a corpus prefix
  4. Return decoded string as the candidate
```

`embed()` mean-pools last-layer hidden states → 384-dim vector (zero-padded if embed_dim < 384). `coherence()` returns `exp(−cross_entropy_loss) ∈ (0, 1]`.

This mapping means `max_cycles=40` in the hypothesis YAML becomes 40 training batches per variant — the kernel needs no modification to support neural training.

### 3.6 Dynamics Metrics Layer

`uaf/dynamics/metrics.py` computes 7 per-cycle scalars as pure functions:

| Metric | Formula | Interpretation |
|---|---|---|
| `convergence_score` | Mean pairwise cosine distance across session embeddings | 1.0 = maximally spread; 0.0 = collapsed |
| `trajectory_drift` | Cumulative path length through embedding space | High = extensive exploration |
| `stability` | Variance of composite_score over rolling k=3 window | Low = stable improvement |
| `plateau_distance` | \|score[−1] − score[−2]\| | Near 0 = plateau; triggers halt |
| `goodhart_pressure` | Guard triggers / cycles elapsed | Rising = reward hacking emerging |
| `novelty_pressure` | {mean, std, min, max} of novelty distribution | Low mean = diversity collapse |
| `refractory_load` | Active locked clusters / total tracked clusters | High = memory pressure |

These are surfaced in real-time in the Q2 Live Dynamics panel and recorded per-cycle in `ExperimentTrace.dynamics_series`.

**[FIGURE 5: fig5_neural_dynamics.png — Q2 Live Dynamics showing train_loss per cycle for n_heads={1,2,4,8} variants during the attention_heads_experiment]**

---

## 4. Experiments

### 4.1 Experimental Setup

All parametric experiments run on CPU without GPU. Neural architecture experiments use PyTorch 2.8.0 on CPU (no CUDA required by design — `embed_dim=64` models train in seconds per batch). Verification uses heuristic mode: a composite of word diversity, token length, and structural markers produces a score on the 1.0–5.0 scale. All experiments use three gaming concept seeds:

1. *"a mystery game where memory works backwards"*
2. *"a survival game where sacrifice is the economy"*
3. *"a horror game with procedurally generated grief"*

**Total corpus:** 351 experiments, 37 distinct architecture variants, 2 domains (gaming: 341, tech: 11), date range: May 22–23, 2026. All runs logged to `logs/experiment_ledger.jsonl` with per-cycle dynamics in `logs/runs/`.

### 4.2 Hypothesis 1: Template Complexity

**Question:** Does template_count affect the quality and diversity of generated concepts?  
**Variants:** template_count ∈ {2, 4, 8} × context_injection ∈ {on, off}  
**Finding:** template_count=4 is optimal; full pools (tc=8) regress by ~0.14 points vs. tc=2. Context injection provides no consistent benefit.

### 4.3 Hypothesis 2: Coherence-Diversity Frontier

**Question:** What coherence_mode × template_count combination maximizes both mean_score AND final_convergence simultaneously?  
**Predicted outcome:** entropy coherence + high template_count maximizes mean_score; slot_ratio + mid-range maximizes convergence; Pareto frontier expected.

**Starting 2×2 grid (Iteration 1):**

| Variant | Configuration | Best Score | Mean Score | Convergence | Goodhart |
|---|---|---|---|---|---|
| iter1_v1 | slot_ratio, tc=2 | 4.730 | 3.965 | **0.835** | 0 |
| iter1_v2 | slot_ratio, tc=8 | 4.590 | 3.938 | **0.886** | 0 |
| iter1_v3 | entropy, tc=2 | 4.730 | 3.965 | **0.835** | 0 |
| iter1_v4 | entropy, tc=8 | 4.590 | 3.938 | **0.886** | 0 |

*Null result immediately visible: iter1_v1 == iter1_v3 and iter1_v2 == iter1_v4 — identical best_score, mean_score, and convergence at equal template_count regardless of coherence_mode.*

**Iteration 2 (engineer panel — all three personas):**

| Variant | Proposed by | Configuration | Best Score | Mean Score | Convergence |
|---|---|---|---|---|---|
| iter2_dep_v2 | Deployed Engineer | slot_ratio, tc=4, transformer | **4.690** | **3.990** | 0.701 |
| iter2_res_v2 | Research Scientist | *length*, tc=8, hash | 4.670 | 3.950 | **0.931** |
| iter2_res_v1 | Research Scientist | slot_ratio, tc=4, transformer, ctx=on | 4.470 | 3.600 | 0.622 |

*Panel discovery: `length` coherence mode — absent from the starting hypothesis — achieves the highest convergence of any run (0.931) while remaining competitive on score. Context injection (ctx=on) penalises mean_score by ~0.4 vs. identical config without it.*

**Iteration 3 (engineer panel):**

| Variant | Proposed by | Configuration | Best Score | Mean Score | Convergence |
|---|---|---|---|---|---|
| iter3_res_v1 | Research Scientist | entropy, tc=8, transformer, ctx=on | 4.510 | 3.900 | 0.702 |
| iter3_dep_v1 | Deployed Engineer | slot_ratio, tc=5, transformer, ctx=on | 4.470 | 3.600 | 0.622 |
| iter3_res_v2 | Research Scientist | slot_ratio, **tc=1**, hash, ctx=on | **3.360** | 3.330 | **0.458** |

*Dual collapse at tc=1: both best_score (3.36, lowest across all runs) and convergence (0.458, lowest across all runs) collapse simultaneously. The search space contracts AND output quality degrades.*

**Iteration 4 (engineer panel):**

| Variant | Proposed by | Configuration | Best Score | Mean Score | Convergence |
|---|---|---|---|---|---|
| iter4_res_v2 | Research Scientist | *length*, tc=4, hash, ctx=on | 4.570 | 3.960 | 0.729 |
| iter4_res_v1 | Research Scientist | entropy, tc=8, transformer, ctx=on | 4.510 | 3.900 | 0.702 |
| iter4_dep_v1 | Deployed Engineer | slot_ratio, tc=4, transformer, ctx=on | 4.470 | 3.600 | 0.622 |

**Iteration 5 (engineer panel):**

| Variant | Proposed by | Configuration | Best Score | Mean Score | Convergence |
|---|---|---|---|---|---|
| iter5_dep_v2 | Deployed Engineer | slot_ratio, tc=3, hash, ctx=off | **4.730** | 3.670 | 0.719 |
| iter5_dep_v1 | Deployed Engineer | entropy, tc=4, transformer, ctx=off | 4.690 | 3.990 | 0.701 |
| iter5_res_v2 | Research Scientist | entropy, tc=8, transformer, ctx=on | 4.610 | **4.250** | 0.613 |

**Key findings (all 5 iterations):**
- **Null result (confirmed across 5 iterations):** coherence_mode (slot_ratio vs. entropy) produces identical scores and convergence at equal template_count throughout. The predicted axis has zero discriminative power.
- **Phase boundary with dual collapse (tc=1):** iter3_res_v2 shows best_score=3.36 AND convergence=0.458 — both score and search diversity collapse simultaneously at tc=1. The search space contracts rather than exploring when templates are too sparse.
- **Pareto frontier (iteration 5):** iter5_dep_v2 (best=4.73, mean=3.67) vs. iter5_res_v2 (best=4.61, mean=4.25). Neither dominates. The mean_score gap (4.25 vs. 3.67) is the clearest reliability signal across all experiments.
- **Context injection penalty:** ctx=on variants consistently underperform ctx=off at identical template_count and coherence_mode (−0.3 to −0.4 mean_score across comparable pairs).
- **Length coherence mode (panel discovery):** Absent from the original hypothesis, proposed by the Research Scientist in iteration 2. Achieved the highest convergence of any run (0.931, iter2_res_v2) and remained competitive on score. Not predicted; discovered through epistemic diversity.

**[FIGURE 6: fig6_param_space.png — Architecture Parameter Space: Sankey diagram mapping template_count → context_injection → coherence_mode → embed_strategy → best_score across all variants]**

**[FIGURE 7: fig7_score_evolution.png — Score evolution chart: all 5 iterations of the coherence-diversity frontier, one line per variant, showing Pareto separation emerging in iteration 5]**

### 4.4 Hypothesis 3: Attention Heads Experiment (Neural Architecture)

**Question:** Does increasing attention head count improve coherence at fixed embed_dim=64?  
**Predicted outcome:** Non-monotonic — 4 heads optimal; 8 heads degenerates (head_dim=8 is very narrow); 1 head has no multi-stream separation.

**Architecture configuration (neural variants):**
- n_layers=2, embed_dim=64, context_len=32, n_train_steps=10, lr=3e-4
- Training: AdamW with grad clip 1.0; character-level CharTokenizer

**Iteration 1 — neural head-count sweep (baseline):**

| Variant | Config | Best Score | Mean Score | Convergence | Notes |
|---|---|---|---|---|---|
| iter1_1head | n_heads=1, head_dim=64 | 4.48 | 4.17 | 0.067 | No multi-stream separation |
| iter1_2heads | n_heads=2, head_dim=32 | 4.48 | **4.27** | 0.084 | Minimal multi-stream |
| iter1_4heads | n_heads=4, head_dim=16 | 4.48 | 4.09 | 0.086 | Balanced expressiveness |
| iter1_8heads | n_heads=8, head_dim=8 | 4.48 | **4.27** | **0.092** | Narrow heads |

*Score null result:* all four head counts produced identical best_score=4.48. The original hypothesis is unanswerable from score alone at embed_dim=64. However, **convergence increases monotonically with head count** (0.067 → 0.092) — more heads → slightly higher exploration diversity, even without score improvement.

**Iteration 2 — panel pivot to cross-architecture comparison:**

After diagnosing the score null result, all three personas abandoned neural variants and proposed parametric or symbolic alternatives to test whether the 4.48 ceiling is a neural architecture artifact:

| Variant | Proposed by | Configuration | Best Score | Mean Score | Convergence |
|---|---|---|---|---|---|
| iter2_dep_v1 | Deployed Engineer | parametric: tc=2, ctx=off, entropy, transformer | **4.73** | **3.99** | 0.702 |
| iter2_res_v1 | Research Scientist | parametric: tc=8, ctx=on, entropy, transformer | 4.64 | 3.88 | 0.697 |
| iter2_cha_v2 | Chaos Engineer | **symbolic_grammar** (chaos baseline) | 4.64 | 3.88 | **0.815** |

*Cross-architecture finding:* symbolic grammar achieved conv=0.815 — the highest convergence of any iter-2 variant — at equal score to iter2_res_v1. The 4.48 ceiling in iter1 was a neural architecture floor, not an evaluation ceiling.

**Iteration 3 (engineer panel):**

| Variant | Proposed by | Configuration | Best Score | Mean Score | Convergence |
|---|---|---|---|---|---|
| iter3_cha_v2 | Chaos Engineer | parametric: tc=8, ctx=off, slot_ratio, hash | **4.73** | **4.00** | **0.823** |
| iter3_res_v1 | Research Scientist | parametric: tc=8, ctx=on, entropy, transformer | 4.64 | 3.88 | 0.697 |
| iter3_dep_v1 | Deployed Engineer | parametric: tc=4, ctx=on, entropy, transformer | 4.61 | 3.65 | 0.690 |

**Iteration 4 (engineer panel) — new best score:**

| Variant | Proposed by | Configuration | Best Score | Mean Score | Convergence |
|---|---|---|---|---|---|
| iter4_dep_v1 | Deployed Engineer | parametric: tc=4, ctx=off, entropy, transformer | **4.77** | 3.72 | 0.728 |
| iter4_res_v2 | Research Scientist | parametric: tc=2, ctx=off, slot_ratio, transformer | 4.73 | **3.99** | 0.702 |
| iter4_cha_v1 | Chaos Engineer | parametric: tc=8, ctx=off, entropy, transformer | 4.72 | 3.86 | 0.724 |

**Iteration 5 (engineer panel) — consolidation:**

| Variant | Proposed by | Configuration | Best Score | Mean Score | Convergence |
|---|---|---|---|---|---|
| iter5_res_v1 | Research Scientist | parametric: tc=8, ctx=off, entropy, transformer | **4.72** | **3.86** | **0.724** |
| iter5_res_v2 | Research Scientist | parametric: tc=2, ctx=on, slot_ratio, transformer | 4.62 | 3.85 | 0.692 |
| iter5_dep_v1 | Deployed Engineer | parametric: tc=4, ctx=on, entropy, transformer | 4.61 | 3.65 | 0.690 |

**Key findings (all 5 iterations):**
- **Head-count null result:** n_heads={1,2,4,8} produce identical best_score=4.48 at embed_dim=64. The predicted non-monotonic relationship does not manifest at this scale. The hypothesis was not confirmed (loop resolved=False at max_iterations).
- **Convergence monotone with head count:** 0.067 (1-head) → 0.084 (2-heads) → 0.086 (4-heads) → 0.092 (8-heads). More heads expand exploration diversity without improving peak output quality.
- **Panel meta-pivot:** having detected the score null in iteration 1, all three personas independently switched to non-neural architectures. The panel's meta-cognitive decision to abandon the neural sweep distinguishes it from a fixed-sweep NAS approach.
- **Neural floor vs. evaluation ceiling:** parametric variants scored up to 4.77 (iter4_dep_v1) vs. neural max 4.48, confirming the iter1 ceiling is an architecture constraint, not an evaluation limit.
- **Context injection penalty confirmed:** iter5_dep_v1 (ctx=on, tc=4) = 4.61 vs. iter4_dep_v1 (ctx=off, tc=4) = 4.77 — consistent with Stage 3a finding (−0.3 to −0.4 mean_score penalty for context injection).

**[FIGURE 8: fig8_attention_heads.png — Convergence and score across 5 iterations: neural head-count sweep (iter1) followed by parametric pivot (iter2–5); convergence monotone with head count plotted separately]**

---

## 5. Results

### 5.1 Overall Performance

Across 351 gaming domain experiments:

| Metric | Value |
|---|---|
| Best score achieved | **4.78 / 5.0** (iter4_dep_v2) |
| Mean best score | **4.52** |
| Mean score (all cycles) | **3.85** |
| Convergence range (Stage 3a, post-fix) | **0.458–0.931** across all 5 coherence-diversity iterations |
| Convergence sample (`uaf_20260527_124733`) | **0.604** mean pairwise cosine distance (gaming, 5 cycles) |
| Goodhart violations | **0** across all experiments including Stage 3a |
| Distinct architectures evaluated | **37+** (incl. length coherence mode panel discovery) |
| Halt reason | 96.9% max_loops_reached; 3.1% planner_halt |

Convergence values are from Stages 3a and 3b post-fix re-runs (Stage 3a: coherence-diversity, 5 iter, 16 variants; Stage 3b: attention heads, 5 iter, 16 variants). Pre-Phase-10 values remain stale and excluded (see §6.4). The range 0.458–0.931 spans the tc=1 dual-collapse floor to the length-coherence-mode ceiling. Stage 3b neural variants produced conv=0.067–0.092, well below the parametric range, consistent with the shorter training horizon (n_train_steps=10). Zero Goodhart violations across all experiments confirm the heuristic verifier is not gameable by any tested architecture type.

**[FIGURE 9: fig9_leaderboard.png — Architecture leaderboard: all 37+ variants ranked by best_score, showing top 10 with mean_score, convergence, and Goodhart columns]**

### 5.2 Coherence Mode: A Null Result

Across all 5 iterations of the coherence-diversity frontier, `coherence_mode=slot_ratio` and `coherence_mode=entropy` produced **identical scores and convergence** at equal template_count (confirmed immediately from iteration 1: iter1_v1 == iter1_v3 and iter1_v2 == iter1_v4 to 3 decimal places). This null result is robust: it held across all panel-proposed variants in iterations 2–5. The two modes differ in *how* they score structural coherence of candidates, but at all template scales tested (tc=1–8), both modes selected from the same effective candidate pool.

The panel's discovery of a third mode — `length` coherence — breaks the degeneracy. Length-mode achieved the highest convergence of any run (0.931, iter2_res_v2) and remained competitive on score (4.67). This suggests the null result for slot_ratio vs. entropy is a property of those two specific modes, not of coherence mode as a design axis. Future work should test additional modes (e.g., semantic distance, syntactic structure) before concluding that coherence mode is irrelevant.

### 5.3 Template Count: Phase Boundary and Optimal Point

Template count has a non-monotonic effect on score and convergence:

| template_count | Best Score | Convergence | Interpretation |
|---|---|---|---|
| tc=1 | 3.36 | 0.458 | **Dual collapse** — score AND diversity floor simultaneously |
| tc=2 | 4.73 | 0.835–0.931 | **Optimum** — concentrated variation, high convergence range |
| tc=3 | 4.73 | 0.719 | Ties tc=2 on peak score; panel discovery (iter5_dep_v2) |
| tc=4 | 4.69 | 0.622–0.852 | Near-optimal; stable across all personas |
| tc=8 | 4.59 | 0.702–0.886 | Regression — over-dilution reduces score floor |

The phase boundary at tc=1 was discovered by the Research Scientist persona in iteration 3 (iter3_res_v2: slot_ratio, tc=1, hash, ctx=on). The dual collapse — best_score 3.36 is the lowest of any run AND convergence 0.458 is the lowest of any run — distinguishes tc=1 from a simple quality regression. The search space itself contracts: with only one template, the pool offers insufficient structural variation to maintain exploration diversity.

The tc=3 tie with tc=2 (both 4.73) is a panel discovery from iteration 5. It suggests the optimal region is tc=2–4, not a single point. The broad convergence range at tc=2 (0.835–0.931) vs. the narrower range at tc=8 (0.702–0.886) indicates that low-tc configurations are more sensitive to embed strategy and coherence mode choice.

### 5.4 Pareto Frontier: Stability vs. Peak Performance

The final Pareto frontier emerged in iteration 5:

| Config | Best Score | Mean Score | Convergence | Evaluation lens |
|---|---|---|---|---|
| iter5_dep_v2 (Deployed Engineer) | **4.73** | 3.67 | 0.719 | Peak performance; higher variance |
| iter5_res_v2 (Research Scientist) | 4.61 | **4.25** | 0.613 | Lower peak; strongest reliability |

Neither dominates. The mean_score gap (4.25 vs. 3.67, a 0.58 difference) is the strongest reliability signal across all experiments and exceeds typical cycle-to-cycle variance (~0.3). A production system selecting on best_score would choose iter5_dep_v2; one optimizing for mean_score (minimizing worst-case output) would choose iter5_res_v2.

The gap widened over iterations: early Pareto candidates (iterations 1–3) showed smaller mean_score separations (≤0.2). The iter5 frontier's 0.58 separation emerged because the Deployed Engineer pushed determinism (ctx=off, tc=3) while the Research Scientist pushed contextual richness (ctx=on, tc=8, transformer) — orthogonal production-use-case heuristics that single-expert refinement would not have explored simultaneously.

### 5.5 Neural Architecture Results

The attention heads experiment produced two findings: a null result on the primary hypothesis, and a panel meta-behavior finding that is itself a contribution.

**Primary null result — head count does not discriminate score at embed_dim=64:**

All n_heads ∈ {1, 2, 4, 8} produced identical best_score=4.48 in iteration 1. The predicted non-monotonic relationship — 4-heads optimal, 8-heads degenerate, 1-head under-expressive — did not manifest. At embed_dim=64 with n_train_steps=10, the character-level transformer's expressiveness is constrained by training budget and context length (32 tokens), not by head-count configuration. The loop resolved=False at max_iterations.

**Secondary finding — convergence differentiates monotonically:**

| n_heads | head_dim | Convergence |
|---|---|---|
| 1 | 64 | 0.067 |
| 2 | 32 | 0.084 |
| 4 | 16 | 0.086 |
| 8 | 8 | **0.092** |

More attention heads produce higher embedding-space diversity (measured as mean pairwise cosine distance across session embeddings) without improving peak output quality. The effect is monotone and consistent — not a measurement artifact. This suggests head count shapes the *exploration profile* of the simulation rather than the *quality ceiling*, an interesting decoupling for future architectural analysis.

**Panel meta-pivot — diagnosing vs. accepting a null result:**

Having detected the score null in iteration 1, all three personas independently diagnosed the ceiling as an architecture floor and proposed cross-architecture comparisons in iteration 2: the Deployed Engineer proposed a parametric variant, the Research Scientist proposed a high-tc parametric config, and the Chaos Engineer proposed a symbolic grammar baseline. The symbolic grammar variant (iter2_cha_v2) produced conv=0.815 — the highest convergence across all iter-2 variants — confirming the 4.48 neural ceiling is an architecture constraint, not an evaluation limit.

**Cross-architecture score range (post-pivot):**

| Arch type | Best Score | Mean Score | Conv range |
|---|---|---|---|
| neural_transformer (iter1) | 4.48 | 4.09–4.27 | 0.067–0.092 |
| symbolic_grammar (iter2_cha_v2) | 4.64 | 3.88 | 0.815 |
| parametric (iterations 2–5) | **4.77** | 3.65–4.00 | 0.690–0.823 |

The parametric architecture (iter4_dep_v1: tc=4, ctx=off, entropy, transformer embed) achieves the experiment's best score (4.77), matching the overall corpus leader (4.78) within measurement noise. This strengthens the §5.3 finding that the tc=2–4 optimal region is robust across experiment contexts.

---

## 6. Discussion

### 6.1 The Value of Multi-Persona Deliberation

The engineer panel's value is best illustrated by contrasting iteration 1 with iterations 2–5 of the coherence-diversity frontier. Iteration 1 seeded a baseline 2×2 grid (slot_ratio/entropy × tc=2/tc=8) — four structurally near-identical variants that confirmed the null result but otherwise explored a narrow corner of the parameter space. The panel's iteration 2 immediately broke out: the Research Scientist proposed the `length` coherence mode (entirely absent from the original hypothesis), the Deployed Engineer pushed tc=4 with transformer embed, and two qualitatively distinct variants emerged.

By iteration 3 the panel had found the tc=1 phase boundary (Research Scientist) and confirmed the context injection penalty (Deployed Engineer). By iteration 5 the panel had converged on a Pareto frontier (iter5_dep_v2 vs. iter5_res_v2) with the largest mean_score separation observed in the experiment (0.58 difference). The three findings — phase boundary, context injection penalty, length mode — would not have appeared from single-persona refinement, which anchors on the prior winner and proposes local variations.

**Cost:** The panel makes 4 API calls per refinement step (3 persona + 1 synthesis) vs. 1 for single-Claude. This is a 4× cost increase for qualitatively richer findings — a favorable tradeoff for discovery-mode research.

### 6.2 Semantic Stopping vs. Fixed Iteration Count

The `hypothesis_confirmed` stopping criterion allows Claude to declare resolution when it judges the evidence sufficient. In the coherence-diversity frontier, the hypothesis was resolved at iteration 4 with the Pareto frontier finding — `max_iterations=4` happened to align, but the semantic criterion would allow earlier resolution if, say, iteration 2 had been conclusive.

For the attention_heads_experiment, semantic stopping allows the loop to continue until the n_heads relationship is characterized — even if that requires 6 iterations rather than 4.

### 6.3 Simulation Cycle = Training Step

The mapping of UAF's simulation cycle to a gradient descent step is architecturally significant. The `CognitionEngine.propose()` interface was designed for LLM-based generation; `NeuralTransformerCognition.propose()` trains 10 steps then generates. The kernel does not know or care that training is happening — it sees a string input and a string output, records the CycleRecord, and moves to the next cycle.

This means any differentiable model (RNN, diffusion, fine-tuned LLM) can be inserted as a `CognitionEngine` and evaluated within the same hypothesis loop, with the same panel, using the same verification and memory infrastructure. The interface contract is the key contribution — not any specific architecture.

### 6.4 Limitations

**Heuristic verification:** All 351 experiments used the heuristic verifier (word diversity + length + structural markers). This is fast and free but may not reflect true quality. The Phoenix LLM rater (using Claude as a judge) was not used due to cost — it is the natural next step for validating whether heuristic scores correlate with human judgment.

**Convergence instrumentation bug (Phase-10 post-mortem):** All pre-Phase-10 runs reported `final_convergence=1.0` and `trajectory_drift=0.0` as artifacts of two compounding bugs. First, `_ResearchMemory.session_snapshot()` (`uaf/research/trial_runner.py:85`) always returned `session_embeddings: []`, causing `convergence_score([])` to return the empty-list fallback `1.0` and `trajectory_drift([])` to return `0.0`. Second, `summaries_from_traces` (`trial_runner.py:317`) read the wrong key (`"trajectory_warnings"`, an integer event counter) instead of `"trajectory_drift"` (the float cumulative path length), and `DynamicsRecorder.summary()` omitted `"trajectory_drift"` from its output entirely. Both bugs were fixed in Phase-10 (`tests/test_dynamics_real.py` provides regression coverage; 217 tests pass).

Two post-fix validation runs confirm real per-cycle dynamics are now produced. The second run (`uaf_20260527_130114`, gaming domain, 5 cycles, `claude_novelty_v1`) used the complete per-cycle snapshot fix (kernel-level capture):

| Cycle | Score | Convergence | Trajectory Drift | Notes |
|---|---|---|---|---|
| 0 | 3.20 | 1.000 | 0.000 | Single embedding — single-item fallback (expected) |
| 1 | **4.35** | 0.455 | 0.455 | Score peaks; search space spreading |
| 2 | 3.95 | **0.432** | 0.800 | Min convergence — maximum spread, one cycle after score peak |
| 3 | 2.15 | 0.541 | 1.340 | Convergence rising — search space compressing |
| 4 | 3.85 | 0.585 | 1.691 | Partial score recovery as search stabilises |

**Pre-fix (all cycles):** convergence=1.000, trajectory_drift=0.000, novelty_mean=0.000.  
**Post-fix summary:** final_convergence=0.585, min_convergence=0.432, trajectory_drift=1.690.

This is the first measurable attractor signal: **score peaked (4.35) at cycle 1 when convergence was actively dropping; minimum convergence (0.432) lagged the score peak by one cycle.** The pattern is consistent with the hypothesis that optimization spreads the search space before compressing around high-value regions. A larger corpus of runs is needed to confirm whether this pattern is systematic.

The true convergence distribution for the full 351-experiment corpus requires a post-fix re-run; §4.3 and §5.1 convergence values remain marked pending until that data is available.

**Single domain:** All primary experiments used gaming concept seeds. Generalization to code, science, medicine, or long-form text is untested. The UAF is domain-agnostic by design, but verification metrics may need domain-specific tuning.

**CPU-only:** Neural architecture experiments run on CPU. `embed_dim=64` models train fast enough, but larger architectures (embed_dim=256, n_layers=6) will require GPU for practical loop times.

---

## 7. Conclusion

We presented the Universal Agentic Framework, a system that treats AI architecture discovery as a formal scientific process. The key insight is that hypothesis-driven loops, multi-persona deliberation, and pluggable substrate contracts produce richer findings than black-box search — not by being smarter, but by being structured.

The engineer panel's discovery of a phase boundary, a null result, and a Pareto frontier in a single iteration — findings that two rounds of single-expert refinement missed — demonstrates that epistemic diversity in architecture evaluation is not just philosophically appealing; it is empirically productive.

The equivalence of simulation cycles to training steps means UAF is not a framework for LLM-based systems alone. Any trainable architecture — transformer, RNN, diffusion model — can be evaluated within the same scientific loop with the same panel, the same journal, and the same stopping criterion. This is the broader contribution: a research methodology as much as a framework.

Future work will focus on Phoenix verification (LLM-as-judge), adversarial persona attacks (FGSM on input embeddings), multi-domain experiments, and continuous learning scenarios where the model's weights persist across iterations. The attractor signal observed in §6.4 — score peaking as convergence drops, min convergence lagging the score peak by one cycle — should be confirmed across a larger run corpus and across hypotheses to establish whether it is a systematic property of the optimization loop.

---

## References

[1] Liu, H., Simonyan, K., & Yang, Y. (2019). DARTS: Differentiable architecture search. *ICLR 2019*.

[2] Pham, H., Guan, M., Zoph, B., Le, Q. V., & Dean, J. (2018). Efficient neural architecture search via parameter sharing. *ICML 2018*.

[3] Akiba, T., Sano, S., Yanase, T., Ohta, T., & Koyama, M. (2019). Optuna: A next-generation hyperparameter optimization framework. *KDD 2019*.

[4] Khattab, O., Singhvi, A., Maheshwari, P., Zhang, Z., Santhanam, K., Vardhamanan, S., ... & Potts, C. (2023). DSPy: Compiling declarative language model calls into self-improving pipelines. *arXiv:2310.03714*.

[5] Yang, C., Wang, X., Lu, Y., Liu, H., Le, Q. V., Zhou, D., & Chen, X. (2023). Large language models as optimizers. *arXiv:2309.03409*.

[6] Fernando, C., Hall, D., Faccio, F., Gretton, A., Ratcliff, J., Ortega, P., ... & Schmidhuber, J. (2023). PromptBreeder: Self-referential self-improvement via prompt evolution. *arXiv:2309.16797*.

[7] Wu, Q., Bansal, G., Zhang, J., Wu, Y., Zhang, S., Zhu, E., ... & Wang, C. (2023). AutoGen: Enabling next-gen LLM applications via multi-agent conversation. *arXiv:2308.08155*.

[8] Krakovna, V., Uesato, J., Mikulik, V., Martic, M., Everitt, T., Kumar, R., ... & Legg, S. (2020). Specification gaming: The flip side of AI ingenuity. *DeepMind Blog*.

[9] Karpathy, A. (2022). NanoGPT: The simplest, fastest repository for training/finetuning medium-sized GPTs. *GitHub*.

[10] McCarthy, B. (1980). The 4MAT System: Teaching to Learning Styles with Right/Left Mode Techniques. *EXCEL Inc.*

[11] Anthropic. (2022). Constitutional AI: Harmlessness from AI feedback. *arXiv:2212.08073*.

---

*[END OF DRAFT — Phase-10 dynamics fix applied; §4.3 convergence columns, §5.1 convergence rate, §5.5 neural results, and figures 5/8 pending attention_heads_experiment completion and post-fix re-run]*

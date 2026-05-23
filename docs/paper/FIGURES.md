# Screenshot Capture Guide

Capture these figures in order. Most require the Streamlit app running with an experiment loaded.
Save all screenshots to `docs/paper/figures/` with the exact filenames listed.

---

## Status

| # | Filename | Status | Notes |
|---|---|---|---|
| 1 | fig1_ui_overview.png | **PENDING** | Need live experiment running |
| 2 | fig2_interface_diagram.png | **PENDING** | Diagram (draw, not screenshot) |
| 3 | fig3_loop_flowchart.png | **PENDING** | Diagram (draw, not screenshot) |
| 4 | fig4_panel_personas.png | **READY** | Coherence-diversity experiment complete |
| 5 | fig5_neural_dynamics.png | **PENDING** | Wait for attention_heads_experiment |
| 6 | fig6_param_space.png | **DONE** | Copied from hypotheses/newplot.png |
| 7 | fig7_score_evolution.png | **READY** | Coherence-diversity experiment complete |
| 8 | fig8_attention_heads.png | **PENDING** | Wait for attention_heads_experiment |
| 9 | fig9_leaderboard.png | **READY** | 37+ variants already in ledger |

---

## Figure Capture Instructions

### fig1_ui_overview.png — 4MAT Research Workbench
- **What**: Full app window showing the 4-tab layout with a live or completed experiment
- **How**: `streamlit run frontend/app.py`, load any hypothesis YAML, run 1-2 iterations
- **Frame**: Capture the full browser window including all 4 tab headers (Hypothesis / Live Dynamics / Variant Controls / Discovery Journal) plus any active chart in Q2
- **Ideal state**: Q2 Live Dynamics tab visible with score evolution chart showing 2+ iterations
- **Resolution**: At least 1440×900

### fig2_interface_diagram.png — 5-Interface Architecture
- **What**: Box diagram showing the 5 ABCs and their wiring inside SimulationKernel
- **How**: Create in draw.io, Mermaid, or Excalidraw
- **Content**:
  ```
  SimulationKernel
  ├── CognitionEngine ← [ParametricCognition | SymbolicGrammar | NeuralTransformer]
  ├── MemorySystem    ← [ArchiveMemory]
  ├── VerificationEngine ← [HeuristicVerification | PhoenixVerification]
  ├── Planner         ← [CyclePlanner]
  └── RuntimeEnvironment ← [ResearchRuntime]
  ```
- **Note**: Draw arrows showing that SimulationKernel depends on ABCs, not on concrete implementations

### fig3_loop_flowchart.png — ExperimentLoop Flowchart
- **What**: Flowchart of the hypothesis → trial → compare → panel → repeat cycle
- **How**: Create in draw.io or Mermaid
- **Key nodes**: Hypothesis YAML → ControlledTrialRunner → [N × SimulationKernel] → compare_traces → EngineerPanel OR Single-Claude → hypothesis.findings → [stop? yes: report | no: next iteration]
- **Annotation**: Label the stopping criterion branch (max_iterations / score_threshold / hypothesis_confirmed)

### fig4_panel_personas.png — Discovery Journal Panel Cards
- **What**: Q4 Discovery Journal showing the 3 persona cards from iteration 3 of coherence-diversity frontier
- **How**: Load `hypotheses/coherence_diversity_frontier.yaml` in the app (experiment already complete), navigate to Discovery Journal tab, expand iteration 3
- **Frame**: Capture all 3 persona cards (Research Scientist, Deployed Engineer, Chaos Engineer) with their reasoning text visible and confidence scores
- **Highlight**: The Chaos Engineer's tc=1 proposal that found the phase boundary

### fig5_neural_dynamics.png — Neural Architecture Live Dynamics
- **What**: Q2 Live Dynamics showing train_loss per cycle for all 4 n_heads variants
- **How**: Load `hypotheses/attention_heads_experiment.yaml`, run experiment, capture during iteration 1 or after completion
- **Frame**: The 4-subplot dynamics chart: score by cycle, convergence, train_loss curve (per-variant lines in different colors), goodhart pressure
- **Annotation**: Mark where 8-heads shows higher loss than 2-heads (if predicted result holds)

### fig6_param_space.png — Architecture Parameter Space ✓ DONE
- **File**: Already at `docs/paper/figures/fig6_param_space.png`
- **Source**: `hypotheses/newplot.png`
- **What it shows**: Sankey/parallel-coords diagram mapping template_count → context_injection → coherence_mode → embed_strategy → best_score
- **Review**: Check that the chart renders clearly at print resolution; if not, regenerate from the app's Architecture Explorer

### fig7_score_evolution.png — Score Evolution Across Iterations
- **What**: Line chart showing best_score per iteration for all variants across 4 iterations of coherence-diversity frontier
- **How**: Load `hypotheses/coherence_diversity_frontier.yaml`, navigate to Q2 Live Dynamics, select the Score Evolution chart
- **Frame**: 4 iterations on x-axis, best_score on y-axis, one line per variant, different colors
- **Highlight**: The Pareto divergence between dep_v1 and cha_v2 appearing in iteration 3

### fig8_attention_heads.png — Attention Heads per-Cycle Curves
- **What**: Per-cycle train_loss and coherence score for n_heads ∈ {1, 2, 4, 8}
- **How**: During or after attention_heads_experiment, Q2 Live Dynamics tab
- **Frame**: Two subplots side-by-side: (left) train_loss by cycle, (right) coherence by cycle
- **Annotation**: Label the n_heads=8 line if it shows higher loss; circle the cycle where divergence first appears

### fig9_leaderboard.png — Architecture Leaderboard
- **What**: Variant comparison table showing all 37+ variants ranked by best_score
- **How**: Q2 Live Dynamics → Architecture Leaderboard section (or the Architecture Explorer in the Q1 tab)
- **Frame**: Top 15-20 rows visible, columns: variant_id, best_score, mean_score, final_convergence, total_cycles, goodhart_total
- **Highlight**: iter4_dep_v2 at the top (best_score=4.78), and the phase boundary variant (iter3_res_v2, score=3.35) near the bottom

---

## Diagram Resources

For fig2 and fig3 (drawn diagrams), recommended tools:
- **Mermaid** (inline in Markdown, renders in GitHub): `graph TD` syntax
- **Excalidraw** (excalidraw.com): free, exports PNG, hand-drawn style works well for papers
- **draw.io** (diagrams.net): professional boxes, exports at high resolution

---

## Tips for Print Quality

- Export at 2× or 3× screen resolution (retina scale in browser dev tools)
- Use PNG, not JPEG (no compression artifacts on text)
- Minimum 300 DPI for ACM/IEEE submission
- Check that legend text is readable at 8pt (half-column width in two-column format)

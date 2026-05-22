# Research Findings

Numbered emergent discoveries. Each entry records what was found, in which run, and what it implies. Entries are permanent — do not delete or overwrite. Add new findings below existing ones.

---

### Finding #001: Vocabulary Gaming Loop

**Observed:** v4 planning phase (pre-implementation).  
**Finding:** The regex-based `FRICTION_PATTERNS` and `ANTI_OPT_PATTERNS` in `concept_rater.py` are vulnerable to surface-level gaming. The language model can learn to produce concepts containing the target vocabulary ("irreversible", "in a room", "no AI") without those properties being structurally embodied.  
**Evidence:** Anticipated from adversarial ML literature. *Empirically confirmed during v4 verification (20260522):* `ritual_cost_score` returned `0.0` for the cast-iron skillet concept — the run's highest-resonance output, which contains no trigger words from `FRICTION_PATTERNS` despite being structurally saturated with physical substrate, irreversibility, biological signal, and anti-optimization. The pattern bank fails at exactly the concepts the system is searching for.  
**Implication:** These scores are directionally correct as a baseline but will degrade over many generations as the mutation engine discovers the pattern bank. They must not become optimization targets. The empirical failure on the skillet concept is a stronger signal than the theoretical argument: the regex measures surface vocabulary, not structural embodiment, and the gap between them is largest for the most resonant outputs.  
**Next sprint fix:** Replace regex with structural POS-tag scoring: ratio of concrete physical nouns to abstract platform verbs; spatial deixis density; past-tense terminal action markers vs. reversible present-tense operations.

---

### Finding #002: Anti-Optimization Attractor Stability

**Observed:** Run `20260522_043802` — `ai_creative_pipeline` domain, self-evolution seeds.  
**Finding:** High resonance + anti-scalability + anti-automation is a stable attractor. Across 3 refinement cycles and 30 generations, every top-10 concept converged on five shared structural properties: physical substrate over digital state, biological signals as pipeline input, irreversibility as forcing function, non-proxyable human checkpoints, and explicit rejection of optimization.  
**Evidence:** Top candidates include: cast-iron skillet grief ritual (Phoenix 4.10, combined 0.632), Burnout Cartographer (combined 0.567), grief counseling on flip-phones (combined 0.491), hand-stitched field manual (combined 0.482). All five independently include "no AI", physical artifact, and irreversible termination.  
**Implication:** This is not noise. The engine has found a stable region of cultural resonance space that is defined by anti-digital properties. The region's stability across 30 mutations suggests it is a genuine attractor, not a local maximum.

---

### Finding #003: Improvement Loop Degrades Sacred Concepts

**Observed:** Run `20260522_043802`, cycles 2→3 score delta.  
**Finding:** Phoenix score trajectory was 3.65 → 4.10 → 3.95. Cycle 3 scored *lower* despite targeting the weakest criteria (action_clarity=2, platform_fit=3). The improvement loop, by applying optimization pressure to "action_clarity" and "platform_fit", prompted mutations that made the concept more actionable and platform-compatible — which directly degraded its anti-commercial, anti-platform core identity.  
**Evidence:** Score plateau triggered at delta = -0.15 (cycle 3 score: 3.95 vs cycle 2: 4.10). The plateau detection correctly halted the loop at this point.  
**Implication:** Some concepts derive strength from resisting the criteria the improvement loop uses. The improvement loop has an inherent failure mode: it will consistently degrade concepts whose power comes from anti-optimization. The plateau at a score *decline* is the system protecting itself. This is not a bug — it is empirical evidence that certain values are destroyed by being optimized.

---

### Finding #004: Sandbox Economic Signal Separation

**Observed:** Run `20260522_043802`.  
**Finding:** The cast-iron skillet concept scored Phoenix 4.10/5.0 (high cultural resonance) while simultaneously scoring SLOP on the capital sandbox (viral_velocity=0, engaged=0 across all 5 weeks). This is not a measurement failure — it is accurate signal separation.  
**Evidence:** The sandbox `ai_creative_pipeline` agents (VC scout, skeptic engineer, indie builder, creative director) correctly identify that a grief ritual in rural Appalachia has no economic velocity, no viral coefficient, and no platform fit. These are genuine properties of the concept, not defects.  
**Implication:** Economic velocity (capital sandbox) and cultural gravity (Phoenix resonance) are orthogonal axes, not correlated. Modern recommendation systems collapse these together. The architecture has begun separating them. The COUNTER_SIGNAL verdict category encodes this separation structurally.

---

### Finding #005: Physical Substrate as Convergent Memory Model

**Observed:** Run `20260522_043802`, top candidates analysis.  
**Finding:** The most novel concepts (novelty > 0.65) consistently externalized memory into material objects: cast-iron skillet (carbonized fat layers as embedding), grain silo (microbial decomposition as scoring), field manual (ink marginalia as refinement loop), ceramic vessels (breath pressure as mutation input). These physical objects share properties with software memory systems but add thermodynamic cost, scarcity, and irreversibility.  
**Evidence:** 7 of the top 10 candidates across all 30 generations include a physical object that functions as a state store.  
**Implication:** The model has independently rediscovered material computation — the idea that physical objects can serve as information processing substrates. The key difference from digital memory: physical substrates are lossy, scarce, and mortal. These properties appear to be prerequisites for the type of meaning the engine is searching for.

---

### Finding #006: Plateau Detection as Integrity Preservation

**Observed:** Run `20260522_043802`, cycle 2→3.  
**Finding:** Plateau detection (delta < 0.10 threshold) fired when the score *declined* rather than simply stagnating. The implementation (`if delta < PLATEAU_DELTA`) treats negative delta as a plateau since -0.15 < 0.10. This had the effect of halting the loop at the moment the improvement cycle began damaging the concept.  
**Evidence:** Delta = -0.15. Loop exited correctly. Best concept preserved from cycle 2.  
**Implication:** The plateau threshold should remain a signed check (not `abs(delta) < PLATEAU_DELTA`). Score decline is a stronger signal to stop than score stagnation — it indicates the improvement loop has crossed into destructive territory. The signed check correctly treats both as loop-exit conditions.

---

### Finding #007: Agent Calibration Drift as Pruning Signal

**Observed:** v4 architecture review (post-implementation analysis).  
**Finding:** Pruning sandbox agents on output quality (HIT rate) recreates the Goodhart collapse at the agent layer — agents drift toward permissive scoring. The non-circular pruning signal is *calibration drift*: an agent whose verdict distribution entropy collapses toward zero (always-HIT scout, always-SLOP skeptic) is producing noise, not signal. Calibration entropy is orthogonal to the optimization loop because a well-calibrated agent that consistently rejects concepts is as valuable as one that accepts them.  
**Evidence:** Theoretical, derived from sandbox verdict structure analysis. Not yet empirically confirmed in a run.  
**Implication:** Agent auto-pruning is architecturally viable using the existing terminal archive / entropy decay / parent selection primitives — agents are another evolvable artifact class. The PHZ constraint applies to agent variants the same way it applies to concepts: human veto should block agent terminal writes. Implementation proposed for Phase 6.

---

### Finding #008: v5 Hypothesis Testable Without Transformer Modification

**Observed:** v4 architecture review (post-implementation analysis).  
**Finding:** The v5 transformer invariants (volatile KV-cache decay, anti-Goodhart attention repulsion, refractory activation) can be approximated as a prompt-level simulation wrapper around standard Claude API calls, enabling empirical calibration of the v5 hypothesis before committing to custom transformer implementation.  
**Evidence:** The observer effect guard (embedding convergence detection + break-out injection) is already a working implementation of anti-Goodhart attention at the prompt level. Extending this pattern to full-session entropy decay and refractory phrase-cluster lockout is a tractable sprint.  
**Implication:** Build the simulator as the primary research instrument for the v5 hypothesis. Measure whether simulated entropy repulsion produces outputs with higher `ritual_cost_score` and `anti_optimization_score` vs. baseline Claude calls on identical seeds. This is the empirical path to v5 without architectural commitment. Proposed as Phase 5B (parallel to agent auto-pruning Phase 6).

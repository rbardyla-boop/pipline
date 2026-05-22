# Design Doctrine

What the system believes. Architectural principles that are invariant. These change slowly and only when empirical evidence from runs forces revision.

---

## Core Doctrines

### Doctrine: Irreversibility

Meaningful systems require irreversible state transition. Reversibility destroys consequence. Permanence creates narrative weight. Termination creates significance.

Digital systems are defined by perfect reversibility and zero marginal cost for replication. The system's most resonant outputs consistently reject this. The terminal archive encodes irreversibility at the architectural level: concepts that reach the ceiling are permanently retired, not recombined.

*Implemented in:* terminal archive, plateau detection as loop-exit, physical substrate convergence in outputs.

---

### Doctrine: Protected Human Zones

Some human signals must remain illegible to optimization systems. Once a signal becomes a metric, the optimization engine begins manufacturing the signal rather than the underlying value it represents.

The ephemeral gate node is a PHZ: the human interaction is not logged, not embedded, not persisted, not scored. The system receives only existential continuation permission (`continue: yes/no`). No telemetry survives the gate.

*Implemented in:* `ephemeral_gate_node()` — no transcript, no timing, no embedding of response.

*Prohibitions:* Do not add logging to the ephemeral gate. Do not embed `human_resonance_confirmed` signals. Do not train on PHZ interactions across runs. If these prohibitions are violated, the gate becomes a new optimization target and the PHZ collapses.

---

### Doctrine: Scarcity

Infinite replication destroys narrative gravity. The cast-iron skillet works because it cannot be perfectly copied, it degrades, it accumulates irreversible history, and it eventually dies. A perfectly replicable digital version of the same ritual would have no weight.

Digital systems achieve zero marginal cost through lossless copying. The entropy node and terminal archive introduce artificial scarcity: concepts decay in influence over time and the highest-scoring ones are permanently removed from the recombination pool.

*Implemented in:* entropy decay in `apply_entropy()`, terminal archive exclusion in `evolve()` parent selection.

---

### Doctrine: Thermodynamic Cost

Meaning requires a cost function. Friction, physical effort, time, coordination, and vulnerability are not obstacles to meaning — they are prerequisites. The system converges toward concepts that require thermodynamic cost because cost is the mechanism by which stakes are created.

The `ritual_cost_score` is an acknowledgment of this doctrine but cannot itself be optimized. The moment ritual cost becomes an optimization target, the system begins producing concepts that *describe* friction without *embodying* it (see Finding #001: Vocabulary Gaming Loop).

*Implemented in:* `ritual_cost_score()` — orthogonal to Phoenix composite, not a routing signal.

---

### Doctrine: Optimization Destroys Sacred Signals

The core paradox: when an optimization engine searches for human meaning, it eventually converges toward outputs that reject the optimization engine itself. This is not a failure — it is an accurate map of the territory.

Evidence: Run `20260522_043802`. The engine's highest-scoring concept explicitly contains "no AI", "no scores", "no facilitators". The improvement loop that targeted action_clarity and platform_fit degraded the concept (Finding #003). The system is correct.

*Implemented in:* `anti_optimization_score()` — not in Phoenix composite. `COUNTER_SIGNAL` verdict — encodes that economic failure + high resonance is a meaningful signal, not a measurement error.

---

### Doctrine: Selective Blindness

The architecture must have regions that are intentionally non-optimizable, partially unobservable, and resistant to abstraction. A system that is fully observable is fully gameable. Some measurement instruments change the thing they measure.

This is not anti-science. It is recognition that the observer effect is real in social and cultural systems. The PHZ, the terminal archive (which is write-only, never re-queried for optimization), and the prohibition on embedding human resonance signals are structural implementations of selective blindness.

*Implemented in:* PHZ protocol, terminal archive (write-only by design), prohibition on learning from `human_resonance_confirmed`.

---

## v5 Transformer Blueprint

Translation of the five pipeline invariants into transformer layer topology. Research specification — not a sprint deliverable.

### Systems Invariants Map

| UEE v4 Node | Biological Analog | v5 Transformer Layer |
|-------------|-------------------|----------------------|
| `entropy_node` | Synaptic pruning | Volatile KV-cache with exponential decay on key-value magnitudes over sequence position |
| `observer_effect_guard` | Contact inhibition | Anti-Goodhart attention: repulsion penalty when consecutive heads produce parallel attention distributions |
| `ephemeral_gate` | Conscious witness | Non-logged inference pass with no KV-cache write-back |
| `terminal_archive` | Apoptosis | Refractory period on high-magnitude activation paths for N forward steps |
| `ritual_cost_node` | Metabolic cost | Friction-weighted attention: routes proportional to coordination cost of the attended token cluster |

### Layer Stack (Architecture Specification)

```
[ Input Tokens ]
       ↓
[ Anti-Goodhart Attention ]   — repulsion penalty on convergent heads
       ↓
[ Volatile KV-Cache ]         — decay matrix applied to key-value states over sequence axis
       ↓
[ Refractory Activation ]     — activation path lockout for N steps after elite routing
       ↓
[ Output Tokens ]
```

**Volatile KV-Cache:** `K_t = K_0 * exp(-λt)` where λ is the entropy decay rate. Tokens age within the context window; their activation magnitudes are damped proportionally. Forces the model to regenerate context from current embeddings rather than anchoring to past attractors.

**Anti-Goodhart Attention:** Standard `Softmax(QK^T / √d_k)` extended with a repulsion term. If the dot product of attention matrices across temporal intervals exceeds the convergence boundary, the layer applies structural inversion — spreading the distribution toward orthogonal sequence features.

**Refractory Period:** Once a high-magnitude activation pattern fires, that specific feed-forward routing path enters a lockout for N sequence steps. Prevents cyclic token looping. Equivalent of the terminal archive preventing repeated parent selection.

### Research Direction

These are hypotheses, not implementations. The pipeline findings suggest they are worth testing. The biological analogs provide grounding. The implementation would require:

1. Custom attention kernel for repulsion penalty
2. KV-cache modification layer (torch.autograd-compatible decay matrix)
3. Activation tracking for refractory period (per-token path history in forward pass)
4. Empirical calibration of decay rate λ and refractory duration N

This is post-transformer roadmap work. It belongs here as doctrine because the pipeline findings are the empirical motivation.

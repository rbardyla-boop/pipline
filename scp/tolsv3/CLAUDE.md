# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Tangent-Oriented Liquid State (TOLS) v3** — a research implementation of a novel oscillatory associative memory architecture. The system models N multi-dimensional Kuramoto oscillators on tangent bundles (unit sphere S^{D-1}), using a tensor pseudoinverse coupling rule for pattern storage and retrieval.

## Running Experiments

No formal build system. Direct Python execution:

```bash
# Full experiment pipeline (in order)
python3 step1_keff_ablation.py      # Adaptive K impact analysis
python3 step2_basin_radius.py       # Basin depth sweeps
python3 step3_package.py            # Consolidates tols/ package from phase2 source
python3 step4_mnist_real.py         # MNIST classification benchmarks
python3 step5_decision.py           # Decision table compilation

# Via CLI (requires step3_package.py to have been run first)
python -m tols.cli --experiment 1 --P 16 --N 32 --D 8 --K 4.0 --seed 42
python -m tols.cli --experiment 2 --P 8 --seed 42

# Supplementary
python3 hopfield_testbed.py         # Classical Hopfield comparison
python3 whitening_experiment.py     # Gram matrix conditioning
python3 argmax_experiment.py        # MNIST argmax classification
python3 basin_bound_verify.py       # Energy monotonicity verification
```

**Dependencies**: `numpy` (required), `scikit-learn` (MNIST), `opencv-python` (artifact_lens subproject).

## Quick Functional Test

```bash
python3 -c "
from tols.core import TangentTOLS, make_orthogonal_patterns, corrupt
import numpy as np
rng = np.random.RandomState(42)
net = TangentTOLS(n_units=32, pattern_dim=8, coupling_strength=4.0, coupling_rule='tensor_pseudo')
patterns = make_orthogonal_patterns(2, 32, 8, rng)
for p in patterns: net.store_pattern(p)
cue = corrupt(patterns[0], 0.15, np.random.RandomState(99))
recalled, steps, diag = net.recall(cue, max_steps=1000, log=False)
print(f'Similarity: {net.pattern_similarity(recalled, patterns[0]):.3f}')
"
```

## Architecture

### Core Algorithm (`tols/core.py` / `tols_v3_phase2.py`)

**`TangentTOLS`** is the central class:

- **State**: `X` — an N×D matrix of unit vectors (each row lives on S^{D-1})
- **Storage**: `store_pattern(p)` adds normalized pattern, rebuilds Gram matrix `G = P^T P`
- **Coupling**: `tensor_pseudo` rule solves `alpha = G^{-1} @ overlaps` to compute forces; avoids crosstalk from correlated patterns
- **Dynamics loop** in `recall()`:
  1. `_overlaps()` — Frobenius inner products `⟨p_k, X⟩`
  2. `_raw_force_tensor_pseudo()` — weighted sum of stored patterns
  3. `_project_tangent()` — projects forces onto tangent space of sphere at each unit
  4. Euler integration: `X ← X + dt * F_tangent`, renormalize
  5. Convergence check: max change < tolerance
- **Energy**: `compute_energy()` provides Lyapunov function for stability monitoring

**Key constants** (defaults used throughout experiments):
- `N=32` units, `D=8` pattern dimension, `K=4.0` coupling strength, `dt=0.005`, `max_steps=1000`
- Faithful recall threshold: per-unit cosine ≥ 0.95
- Basin threshold: faithful rate ≥ 80% at given corruption level

### Experiment Modules

- **`tols/experiments.py`**: `run_faithful_rate(P, ...)` and `run_basin_radius(P, ...)` — primary metrics
- **`tols/cli.py`**: CLI wrapper outputting JSON metrics (faithful_rate, basin_radius, k_eff, timing)
- **Phase files** (`tols_v3_phase2.py`, `phase3.py`, `phase4.py`): standalone self-contained experiment scripts with embedded TangentTOLS implementations; the `tols/` package is extracted from phase2 by `step3_package.py`

### Research Phases

| File | Purpose |
|------|---------|
| `tols_v3_testbed.py` | Phase 1: Initial design and baseline |
| `tols_v3_phase2.py` | Phase 2: Tensor pseudoinverse coupling (main innovation) |
| `tols_v3_phase3.py` | Phase 3: Adversarial stress tests, correlated patterns |
| `tols_v3_phase4.py` | Phase 4: Scale-up and refinement |

### Artifact Lens Subproject (`artifact_lens_project/`)

Independent forensic image analysis pipeline. Architecture: Ladder (physics-based) → FRW (feature reliability weighting) → Segmentation → Validator (semantic). Not directly coupled to the TOLS core.

## Key Metrics

- **Faithful recall rate**: fraction of trials where mean per-unit cosine ≥ threshold
- **Basin radius**: maximum corruption fraction maintaining ≥ 80% faithful rate
- **Capacity (α)**: pattern count P / unit count N
- **Gram condition number (κ)**: numerical stability of pseudoinverse; high κ indicates near-singular coupling
- **Energy monotonicity**: verified in `basin_bound_verify.py` — confirms Lyapunov stability

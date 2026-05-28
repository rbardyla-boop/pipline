# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Artifact Lens v1.2.5** — a forensic image analysis pipeline that detects composites, AI-generated images, and laundered photos using physics-based JPEG compression analysis.

## Running the Pipeline

```bash
# Activate the local venv first
source .venv/bin/activate

# Full pipeline — processes all images in tests/, creates dummy if empty
python3 main.py

# Stress test — asserts organic images don't drift to COMPOSITE/SYNTHETIC
python3 tests/stress_suite.py tests/dummy_test.png

# kappa-variance calibration study (requires splice_photo_screenshot.png and synth_gradient.png in tests/)
python3 tests/kvar_calibration.py

# Static syntax check of the entire package
python3 -c "
import ast, pathlib, sys
errors = []
for f in sorted(pathlib.Path('artifact_lens').glob('*.py')):
    try: ast.parse(f.read_text()); print(f'  OK  {f}')
    except SyntaxError as e: errors.append(str(e)); print(f'  FAIL {f}: {e}')
sys.exit(len(errors))
"

# Quick contract verification (run from project root)
python3 -c "
from artifact_lens.core import ArtifactLens
r = ArtifactLens().process_image('tests/dummy_test.png')
assert len(r['ladder_data']) == 19 and 'ela_map' in r['ladder_data'][0]
print('Contract OK:', r['structural_class'])
"
```

**Dependencies**: `opencv-python`, `numpy`, `matplotlib` (required); `onnxruntime` (optional — falls back to feature-proxy without it).

## Architecture

```
main.py
  └─ ArtifactLens.process_image(path)          ← core.py
       ├─ CompressionLadder.run()               ← compression_ladder.py
       │    19 JPEG quality rungs (Q=100→10, step -5)
       │    Per rung: ela, fft, noise, kappa, disagreement, ela_map
       ├─ FeatureReliabilityWeighter            ← reliability.py
       │    compute_weights()                   → {ela, fft, noise} normalised (sum=1.0)
       │    compute_weighted_disagreement()     → Δw (FRW gate scalar)
       ├─ TrajectoryAnalyzer.analyze_trajectory(delta_w=Δw)  ← dynamics.py
       │    kappa profile:      stable / degrading / nonlinear / unstable
       │    conflict profile:   coherent / tension / conflict
       │    → structural_class string
       ├─ [only if COMPOSITE] ManifoldSegmenter ← segmentation.py
       │    ELA heatmap → fault-line ROIs via contour detection
       ├─ [only if COMPOSITE] LatentValidator   ← validator.py
       │    ONNX or 50-dim feature-proxy cosine distance
       │    → may override verdict to ORGANIC / COMPLEX_TEXTURE
       └─ ForensicReporter.generate_report()    ← dashboard.py
            2×3 matplotlib Agg grid → outputs/FORENSIC_<name>.png
```

### Critical design invariant — the Meme Trap

`FeatureReliabilityWeighter` produces Δw = Σ(w_f · σ_f²), which is passed to `TrajectoryAnalyzer` **as a modulator only** — it does not replace the raw `disagreement` values in the ladder. When Δw < 0.10 (FRW gate), the conflict threshold is raised 2.5×, preventing a single spiking feature (e.g., ELA on text overlays) from triggering a false COMPOSITE. Replacing raw disagreement with weighted values would break the profile classifier's calibrated thresholds.

### Verdict taxonomy

| Class | Meaning |
|---|---|
| `ORGANIC` | Real photo, minimal cross-rung conflict |
| `SYNTHETIC (OVER-COHERENT)` | AI-generated — too stable across ladder |
| `COMPOSITE (MANIFOLD COLLISION)` | Multiple compression origins |
| `LAUNDERED / COMPRESSED` | Real photo with prior compression history |
| `MALFORMED / ADVERSARIAL` | High-conflict, unstable |
| `ORGANIC / COMPLEX_TEXTURE` | COMPOSITE downgraded after semantic gate |
| `UNKNOWN / INDETERMINATE` | kappa/conflict profile combination not in map |

## Package Layout

The canonical package is `artifact_lens/`. The `artifact_lens_project/` directory is an older parallel version and should not be confused with the active code.

- `artifact_lens/core.py` — `ArtifactLens` orchestrator
- `artifact_lens/compression_ladder.py` — `CompressionLadder` (19 rungs, stores `ela_map` in every rung dict)
- `artifact_lens/reliability.py` — `FeatureReliabilityWeighter`
- `artifact_lens/dynamics.py` — `TrajectoryAnalyzer` (primary classifier)
- `artifact_lens/analyzer.py` — re-export alias for `TrajectoryAnalyzer`
- `artifact_lens/segmentation.py` — `ManifoldSegmenter`
- `artifact_lens/segmenter.py` — re-export alias for `ManifoldSegmenter`
- `artifact_lens/validator.py` — `LatentValidator` (ONNX or feature-proxy)
- `artifact_lens/dashboard.py` — `ForensicReporter` (matplotlib Agg, non-interactive)
- `models/tols_semantic_v1.2.onnx` — optional ONNX model (absent → feature-proxy)
- `tests/stress_suite.py` — forensic gauntlet; exit 0 = pass, 1 = structural drift
- `tests/kvar_calibration.py` — threshold calibration study for κ-variance separation
- `outputs/` — `FORENSIC_*.png` reports (auto-created)

## Known Failure Modes

| Symptom | Fix |
|---|---|
| `dummy_test.png → SYNTHETIC` | `core.py` must pass raw `ladder_results` (not a weighted copy) to `analyze_trajectory` |
| Report PNG black/blank | `matplotlib.use('Agg')` must appear before any other matplotlib import in `dashboard.py` |
| `KeyError: 'ela_map'` | `compression_ladder.py` stores `ela_map` in every rung — verify `QUALITY_STEPS = list(range(100, 9, -5))` (19 steps) |
| `stress_suite.py` exit 1 | Check `frw_gate` in `dynamics.py` (default 0.10); raise to 0.15 for high-noise cameras |
| `ladder_data` has ≠ 19 steps | Old stub in place — rebuild from `ARTIFACT_LENS_BUILD.md §3` |

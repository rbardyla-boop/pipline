"""
STEP 3: PACKAGE CONSOLIDATION
Creates tols/ package with core, experiments, and cli modules.
TangentTOLS internals copied verbatim — no refactoring.
"""

import os, sys, shutil, subprocess, time

WDIR = os.path.dirname(os.path.abspath(__file__))
TOLS_DIR = os.path.join(WDIR, "tols")
PHASE2 = os.path.join(WDIR, "tols_v3_phase2.py")

t0 = time.time()
print("=" * 72)
print("STEP 3: PACKAGE CONSOLIDATION")
print("=" * 72)

# ------------------------------------------------------------------
# Read phase2 source to extract pieces
# ------------------------------------------------------------------
with open(PHASE2) as f:
    phase2_src = f.read()

# ------------------------------------------------------------------
# core.py  — TangentTOLS + generators + corruption (verbatim copy)
# We copy the entire phase2 module body, stripping only the
# module-level docstring block so it re-documents cleanly.
# ------------------------------------------------------------------
os.makedirs(TOLS_DIR, exist_ok=True)

core_src = '''\
"""
tols/core.py
TangentTOLS class, pattern generators, and corruption utilities.
Copied verbatim from tols_v3_phase2.py — no functional changes.
"""
''' + phase2_src.split('"""', 2)[-1].lstrip()   # strip leading docstring, keep rest

with open(os.path.join(TOLS_DIR, "core.py"), "w") as f:
    f.write(core_src)

print("  Wrote tols/core.py")

# ------------------------------------------------------------------
# experiments.py — wrappers with timing
# ------------------------------------------------------------------
exp_src = '''\
"""
tols/experiments.py
Importable experiment functions with timing wrappers.
"""

import time
import numpy as np
from typing import Dict
from .core import (
    TangentTOLS, make_orthogonal_patterns, make_random_patterns, corrupt
)

_N, _D = 32, 8
_FAITHFUL_THR = 0.95
_PASS_THR = 0.80


def _build(N, D, K, patterns, adaptive_K=True, seed=0):
    net = TangentTOLS(
        n_units=N, pattern_dim=D, coupling_strength=K,
        dt=0.005, coupling_rule="tensor_pseudo",
        adaptive_K=adaptive_K, seed=seed,
    )
    for p in patterns:
        net.store_pattern(p)
    return net


def run_faithful_rate(P, N=_N, D=_D, base_K=4.0, adaptive_K=True,
                      corruption=0.15, n_trials=10, max_patterns=8,
                      seed=42) -> Dict:
    """Measure faithful recall rate at a given pattern count P."""
    t0 = time.time()
    rng = np.random.RandomState(seed + P)
    try:
        patterns = make_orthogonal_patterns(P, N, D, rng)
    except ValueError as e:
        return {"P": P, "faithful_rate": 0.0, "error": str(e), "elapsed_s": 0}

    net = _build(N, D, base_K, patterns, adaptive_K=adaptive_K, seed=seed)
    faithful, total = 0, 0
    for pi in range(min(P, max_patterns)):
        target = patterns[pi]
        for trial in range(n_trials):
            tr = np.random.RandomState(seed + P * 10000 + pi * 100 + trial)
            cue = corrupt(target, corruption, tr)
            try:
                recalled, _, _ = net.recall(cue, max_steps=1000, tol=1e-5, log=False)
                if net.pattern_similarity(recalled, target) >= _FAITHFUL_THR:
                    faithful += 1
            except np.linalg.LinAlgError:
                pass
            total += 1
    return {
        "P": P,
        "faithful_rate": faithful / total if total > 0 else 0.0,
        "total_trials": total,
        "elapsed_s": time.time() - t0,
    }


def run_basin_radius(P, N=_N, D=_D, base_K=4.0, adaptive_K=True,
                     n_trials=20, seed=42) -> Dict:
    """Find the basin radius (max corruption with faithful ≥ 0.80) at pattern count P."""
    import numpy as _np
    t0 = time.time()
    rng = _np.random.RandomState(seed + P)
    try:
        patterns = make_orthogonal_patterns(P, N, D, rng)
    except ValueError as e:
        return {"P": P, "basin_radius": 0.0, "error": str(e), "elapsed_s": 0}

    net = _build(N, D, base_K, patterns, adaptive_K=adaptive_K, seed=seed)
    target = patterns[0]
    basin_radius = 0.0

    for corr in _np.arange(0.05, 0.95, 0.05):
        corr = round(float(corr), 2)
        faithful = 0
        for trial in range(n_trials):
            tr = _np.random.RandomState(seed + P * 100000 + int(corr * 1000) * 100 + trial)
            cue = corrupt(target, corr, tr)
            try:
                recalled, _, _ = net.recall(cue, max_steps=1000, tol=1e-5, log=False)
                if net.pattern_similarity(recalled, target) >= _FAITHFUL_THR:
                    faithful += 1
            except _np.linalg.LinAlgError:
                pass
        if faithful / n_trials >= _PASS_THR:
            basin_radius = corr

    return {
        "P": P,
        "basin_radius": basin_radius,
        "k_eff": base_K * N / P if adaptive_K else base_K,
        "elapsed_s": time.time() - t0,
    }
'''

with open(os.path.join(TOLS_DIR, "experiments.py"), "w") as f:
    f.write(exp_src)
print("  Wrote tols/experiments.py")

# ------------------------------------------------------------------
# cli.py
# ------------------------------------------------------------------
cli_src = '''\
"""
tols/cli.py
Command-line interface: python -m tols.cli --experiment 1 --seed 42
"""

import argparse
import json
import sys
import os
from .experiments import run_faithful_rate, run_basin_radius


def main():
    parser = argparse.ArgumentParser(description="TOLS v3 CLI")
    parser.add_argument("--experiment", type=int, choices=[1, 2], required=True,
                        help="1=K_eff ablation faithful rate, 2=basin radius sweep")
    parser.add_argument("--P", type=int, default=16, help="Number of patterns")
    parser.add_argument("--N", type=int, default=32, help="Number of oscillators")
    parser.add_argument("--D", type=int, default=8, help="Pattern dimension")
    parser.add_argument("--K", type=float, default=4.0, help="Base coupling strength")
    parser.add_argument("--adaptive-K", action="store_true", default=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-json", type=str, default=None,
                        help="Write results dict to this JSON file")
    args = parser.parse_args()

    if args.experiment == 1:
        result = run_faithful_rate(
            P=args.P, N=args.N, D=args.D, base_K=args.K,
            adaptive_K=args.adaptive_K, seed=args.seed
        )
    elif args.experiment == 2:
        result = run_basin_radius(
            P=args.P, N=args.N, D=args.D, base_K=args.K,
            adaptive_K=args.adaptive_K, seed=args.seed
        )

    print(json.dumps(result, indent=2))

    if args.output_json:
        with open(args.output_json, "w") as f:
            json.dump(result, f, indent=2)
        print(f"Results written to {args.output_json}")


if __name__ == "__main__":
    main()
'''

with open(os.path.join(TOLS_DIR, "cli.py"), "w") as f:
    f.write(cli_src)
print("  Wrote tols/cli.py")

# ------------------------------------------------------------------
# __init__.py
# ------------------------------------------------------------------
init_src = '''\
"""tols — TOLS v3 oscillatory associative memory package."""
from .core import TangentTOLS
__version__ = "3.0"
__all__ = ["TangentTOLS"]
'''

with open(os.path.join(TOLS_DIR, "__init__.py"), "w") as f:
    f.write(init_src)
print("  Wrote tols/__init__.py")

# ------------------------------------------------------------------
# Smoke test
# ------------------------------------------------------------------
result = subprocess.run(
    [sys.executable, "-c", "from tols.core import TangentTOLS; print('OK')"],
    capture_output=True, text=True, cwd=WDIR
)

if result.returncode == 0 and "OK" in result.stdout:
    verdict = "PASS"
    print(f"\n  Import test: {result.stdout.strip()}")
else:
    verdict = "FAIL"
    print(f"\n  Import test FAILED:")
    print(f"  stdout: {result.stdout}")
    print(f"  stderr: {result.stderr}")

# Copy to outputs
OUT_DIR = os.path.join(WDIR, "outputs", "tols")
if os.path.exists(OUT_DIR):
    shutil.rmtree(OUT_DIR)
shutil.copytree(TOLS_DIR, OUT_DIR)
print(f"  Copied tols/ to {OUT_DIR}")

print(f"\n  VERDICT: {verdict}")
print(f"  Elapsed: {time.time()-t0:.1f}s")

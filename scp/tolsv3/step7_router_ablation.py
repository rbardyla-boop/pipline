"""
Router ablation decision table.

Sweeps three primary hyperparameters — n_steps, K, gate_alpha — measuring
sparsity ratio and signal/noise preservation fidelity on the canonical
4-signal + 4-noise test geometry used in test_tols_router.py.

Mirrors the step5_decision.py pattern in the existing TOLS pipeline.

Output: printed Markdown table + outputs/router_ablation.json
"""

import json
import math
import os
import time

import torch
import torch.nn.functional as F
import torch.utils.benchmark as benchmark

from tols_router import TOLSDynamicEntropyRouter

LN4 = math.log(4)   # ≈ 1.3863  — theoretical max entropy for 4-class uniform

# ---------------------------------------------------------------
# Sweep grid
# ---------------------------------------------------------------
N_STEPS_VALS  = [1, 3, 5, 10]
K_VALS        = [1.0, 4.0, 8.0]
GATE_ALPHA_VALS = [0.0, 0.25, 0.5, 0.75]


# ---------------------------------------------------------------
# Canonical test batch (same geometry as test_tols_router.py)
# ---------------------------------------------------------------

def make_batch():
    """(1, 8, 8): 4 signal tokens + 4 noise tokens."""
    signal = torch.eye(8)[:4]   # aligned with patterns e1..e4
    noise  = torch.eye(8)[4:]   # orthogonal complement e5..e8
    return torch.cat([signal, noise], dim=0).unsqueeze(0)   # (1, 8, 8)


def make_patterns():
    return torch.eye(8)[:4]     # (4, 8)


def build_router(n_steps, K, gate_alpha):
    router = TOLSDynamicEntropyRouter(
        d_model=8, n_patterns=4,
        K=K, n_steps=n_steps, gate_alpha=gate_alpha,
    )
    # Identity projection: geometry passes through unchanged
    with torch.no_grad():
        router.proj.weight.copy_(torch.eye(8))
    router.set_patterns(make_patterns())
    router.eval()
    return router


# ---------------------------------------------------------------
# Single configuration evaluation
# ---------------------------------------------------------------

def evaluate(n_steps, K, gate_alpha, E, n_bench=100):
    router = build_router(n_steps, K, gate_alpha)

    with torch.no_grad():
        _, mask = router(E)

    signal_pass = mask[0, :4].mean().item()
    noise_pass  = mask[0, 4:].mean().item()
    sparsity    = 1.0 - mask.mean().item()

    # Latency via benchmark.Timer (includes warm-up)
    t = benchmark.Timer(
        stmt="router(E)",
        globals={"router": router, "E": E},
        num_threads=1,
    ).timeit(n_bench)
    router_ms = t.mean * 1e3

    return {
        "n_steps":         n_steps,
        "K":               K,
        "gate_alpha":      gate_alpha,
        "signal_pass_rate": signal_pass,
        "noise_pass_rate":  noise_pass,
        "sparsity_ratio":   sparsity,
        "router_ms":        round(router_ms, 4),
    }


# ---------------------------------------------------------------
# Main
# ---------------------------------------------------------------

def main():
    E = make_batch()

    rows = []
    for n_steps in N_STEPS_VALS:
        for K in K_VALS:
            for gate_alpha in GATE_ALPHA_VALS:
                r = evaluate(n_steps, K, gate_alpha, E)
                rows.append(r)

    # --- Print Markdown table ---
    header = (
        f"| {'n_steps':>7} | {'K':>5} | {'alpha':>6} "
        f"| {'sig_pass':>8} | {'noise_pass':>10} | {'sparsity':>8} | {'ms':>8} |"
    )
    sep = "|" + "|".join(["-" * (w + 2) for w in [7, 5, 6, 8, 10, 8, 8]]) + "|"
    print("\n## Router Ablation Decision Table\n")
    print(header)
    print(sep)
    for r in rows:
        print(
            f"| {r['n_steps']:>7} | {r['K']:>5.1f} | {r['gate_alpha']:>6.2f} "
            f"| {r['signal_pass_rate']:>8.3f} | {r['noise_pass_rate']:>10.3f} "
            f"| {r['sparsity_ratio']:>8.3f} | {r['router_ms']:>8.4f} |"
        )

    # --- Assertion: signal tokens always pass when gate_alpha <= 0.5 ---
    violated = [
        r for r in rows
        if r["gate_alpha"] <= 0.5 and r["signal_pass_rate"] < 1.0
    ]
    assert not violated, (
        f"Signal pass rate < 1.0 for gate_alpha <= 0.5 in {len(violated)} configs:\n"
        + "\n".join(str(v) for v in violated)
    )
    print(f"\n[OK] Assertion: signal_pass_rate == 1.0 for all gate_alpha <= 0.5  "
          f"({sum(1 for r in rows if r['gate_alpha'] <= 0.5)} configs checked)")

    # --- Write JSON ---
    os.makedirs("outputs", exist_ok=True)
    out_path = "outputs/router_ablation.json"
    with open(out_path, "w") as f:
        json.dump(rows, f, indent=2)
    print(f"[OK] Results written to {out_path}  ({len(rows)} configurations)")


if __name__ == "__main__":
    main()

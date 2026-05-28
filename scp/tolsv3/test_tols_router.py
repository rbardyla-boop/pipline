"""
Deterministic validation of TOLSDynamicEntropyRouter.

Geometry:
  - 4 memory patterns  = {e₁, e₂, e₃, e₄} ⊂ R^8  (first 4 standard basis vectors)
  - 4 signal tokens    aligned with the patterns  → peak affinity  → H ≈ 0
  - 4 noise tokens     = {e₅, e₆, e₇, e₈}        → zero overlap  → H ≈ ln(4) ≈ 1.3863

Because the pattern subspace is span{e₁…e₄}, the complement span{e₅…e₈} has exactly
zero overlap with every stored pattern, producing uniform affinity and maximal entropy.
Both signal and noise tokens are fixed points of the dynamics (no tangent force).

gate_alpha=0.5 places the threshold ≈ mean + 0.5·std ≈ 1.06, neatly between 0 and ln(4).
"""

import math
import torch
import torch.nn as nn

from tols_router import TOLSDynamicEntropyRouter

LN4 = math.log(4)   # ≈ 1.38629  — theoretical entropy maximum for 4 uniform classes


# ---------------------------------------------------------------------------
# Build router
# ---------------------------------------------------------------------------

def build_router(gate_alpha: float = 0.5) -> TOLSDynamicEntropyRouter:
    router = TOLSDynamicEntropyRouter(
        d_model=8,
        n_patterns=4,
        K=4.0,
        dt=0.005,
        n_steps=5,
        gate_alpha=gate_alpha,
    )

    # Identity projection so token geometry passes through unchanged
    with torch.no_grad():
        router.proj.weight.copy_(torch.eye(8))

    # Patterns: first 4 standard basis vectors on S^7
    P = torch.eye(8)[:4]          # (4, 8)
    router.set_patterns(P)
    return router


# ---------------------------------------------------------------------------
# Construct token batch
# ---------------------------------------------------------------------------

def make_tokens() -> torch.Tensor:
    """Returns E of shape (1, 8, 8): 4 signal + 4 noise tokens."""
    signal = torch.eye(8)[:4]     # (4, 8) — aligned with attractors
    noise  = torch.eye(8)[4:]     # (4, 8) — orthogonal complement of pattern subspace
    return torch.cat([signal, noise], dim=0).unsqueeze(0)  # (1, 8, 8)


# ---------------------------------------------------------------------------
# Entropy trace: Steps 0–5
# ---------------------------------------------------------------------------

def print_entropy_trace(router: TOLSDynamicEntropyRouter, E: torch.Tensor) -> list:
    trace = router.trace_entropy(E, n_trace_steps=5)   # 6 tensors: steps 0..5

    header = f"{'Step':>5}  {'Sig-0':>8} {'Sig-1':>8} {'Sig-2':>8} {'Sig-3':>8}  {'Noi-0':>8} {'Noi-1':>8} {'Noi-2':>8} {'Noi-3':>8}"
    print("\n-- Shannon Entropy Evolution (signal tokens | noise tokens) --")
    print(header)
    print("-" * len(header))

    for step, H in enumerate(trace):
        h = H[0]   # batch dim 0, shape (8,)
        sig = "  ".join(f"{h[i].item():8.4f}" for i in range(4))
        noi = "  ".join(f"{h[i].item():8.4f}" for i in range(4, 8))
        print(f"{step:>5}  {sig}    {noi}")

    print(f"\n  [Reference] ln(4) = {LN4:.6f}")
    return trace


# ---------------------------------------------------------------------------
# Assertions
# ---------------------------------------------------------------------------

def run_assertions(router: TOLSDynamicEntropyRouter, E: torch.Tensor, trace: list) -> None:
    print("\n-- Assertions --")

    # ---- 1. Entropy bounds ----
    H_final = trace[-1][0]         # (8,)  — step 5 entropies
    mean_signal_H = H_final[:4].mean().item()
    mean_noise_H  = H_final[4:].mean().item()

    assert mean_noise_H > 1.30, (
        f"Noise entropy {mean_noise_H:.4f} should be near ln(4)={LN4:.4f}"
    )
    assert mean_signal_H < 0.05, (
        f"Signal entropy {mean_signal_H:.4f} should be near 0"
    )
    print(f"[PASS] Signal entropy:  {mean_signal_H:.6f}  (expected ≈ 0)")
    print(f"[PASS] Noise entropy:   {mean_noise_H:.6f}  (expected > 1.30, reference ln(4) = {LN4:.6f})")

    # ---- 2. Deterministic gating (temperature=0) ----
    _, mask = router(E, temperature=0.0)
    signal_kept = mask[0, :4].sum().item()
    noise_kept  = mask[0, 4:].sum().item()

    assert noise_kept == 0.0, f"All 4 noise tokens must be pruned; {int(noise_kept)} passed"
    assert signal_kept == 4.0, f"All 4 signal tokens must pass; only {int(signal_kept)} passed"
    print(f"[PASS] Sparsity mask: signal={int(signal_kept)}/4 kept, noise={int(noise_kept)}/4 kept")

    # ---- 3. NaN/Inf safety under extreme temperature (T=2.0) ----
    out_hot, mask_hot = router(E, temperature=2.0)
    assert not torch.isnan(out_hot).any(), "NaN detected in output under temperature=2.0"
    assert not torch.isinf(out_hot).any(), "Inf detected in output under temperature=2.0"
    print(f"[PASS] No NaN/Inf under temperature=2.0  (output max={out_hot.abs().max().item():.4f})")

    # ---- 4. Zero-variance fallback (uniform-entropy sequence) ----
    # All tokens set to e₅ → identical entropy → std == 0 → threshold = inf → all pass
    E_uniform = torch.eye(8)[4].unsqueeze(0).unsqueeze(0).expand(1, 6, 8).clone()
    _, mask_uniform = router(E_uniform, temperature=0.0)
    assert mask_uniform.sum().item() == 6, "Zero-variance fallback must pass all tokens"
    print("[PASS] Zero-variance fallback: all tokens pass when std(H) == 0")

    print("\n[OK] All assertions passed.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    torch.manual_seed(0)

    router = build_router(gate_alpha=0.5)
    E = make_tokens()

    trace = print_entropy_trace(router, E)
    run_assertions(router, E, trace)

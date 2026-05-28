"""
Gradient flow verification for TOLSDynamicEntropyRouter.

Three checks:
  1. proj.weight receives non-zero gradients via the entropy sub-graph
  2. Buffers P and W carry no gradients after backward
  3. torch.autograd.gradcheck on the full differentiable sub-graph
     (proj → L2-sphere → Euler evolve → Shannon entropy)

Architecture note on the hard mask
───────────────────────────────────
`mask = (H < threshold).float()` is a hard threshold — it has zero derivative
everywhere (subgradient = 0 at the kink, undefined at the step).  A loss computed
as `gated_E.sum() = (E * mask).sum()` propagates gradients to E (a constant scale
by mask values) but NOT through mask to proj.weight.

The correct gradient path for training proj.weight is through the entropy itself:
  loss = f(H)  →  ∂loss/∂proj.weight = ∂loss/∂H · ∂H/∂proj.weight

In a full model, a downstream cross-entropy loss on the non-pruned tokens acts as
this f(H) surrogate.  For production end-to-end training, wrap the hard mask with
a straight-through estimator or anneal to it via Gumbel-softmax.
"""

import torch
import torch.nn.functional as F
from torch.autograd import gradcheck

from tols_router import TOLSDynamicEntropyRouter


def _build(dtype=torch.float32):
    router = TOLSDynamicEntropyRouter(d_model=8, n_patterns=4).to(dtype)
    P = F.normalize(torch.eye(4, 8), dim=-1).to(dtype)
    router.set_patterns(P)
    return router


# ---------------------------------------------------------------
# Check 1: proj.weight receives non-zero gradients (via entropy)
# ---------------------------------------------------------------

def check_projection_gradient():
    router = _build()
    router.train()

    E = torch.randn(1, 8, 8, requires_grad=True)

    # Route through the differentiable sub-graph: proj → sphere → evolve → entropy.
    # The hard mask in forward() has zero derivative; training proj.weight requires
    # a loss that propagates through H (the entropy), not through the mask output.
    Y = router.proj(E)
    X = F.normalize(Y, p=2, dim=-1, eps=router.eps)
    X = router._evolve(X, temperature=0.0)
    H = router._entropy(X)
    H.mean().backward()

    grad = router.proj.weight.grad
    assert grad is not None,        "proj.weight.grad is None after backward"
    assert grad.abs().max() > 1e-8, "proj.weight.grad is effectively zero"
    print("[PASS] proj.weight receives non-zero gradients via entropy sub-graph")


# ---------------------------------------------------------------
# Check 2: buffers P and W are gradient-isolated
# ---------------------------------------------------------------

def check_buffer_isolation():
    router = _build()
    router.train()

    E = torch.randn(1, 8, 8, requires_grad=True)
    Y = router.proj(E)
    X = F.normalize(Y, p=2, dim=-1, eps=router.eps)
    router._entropy(X).mean().backward()

    assert router.P.grad is None, "Buffer P must not accumulate gradients"
    assert router.W.grad is None, "Buffer W must not accumulate gradients"
    print("[PASS] Buffers P and W are gradient-isolated")


# ---------------------------------------------------------------
# Check 3: numerical gradcheck on the differentiable sub-graph
# ---------------------------------------------------------------

def check_numerical_gradcheck():
    router = _build(dtype=torch.float64)
    router.eval()

    W64 = router.W.double()
    P64 = router.P.double()
    K   = router.K
    dt  = router.dt
    T   = router.n_steps

    def soft_forward(weight: torch.Tensor, E: torch.Tensor) -> torch.Tensor:
        """proj → sphere → evolve → Shannon entropy (fully differentiable)."""
        Y = F.linear(E, weight)
        X = F.normalize(Y, p=2, dim=-1, eps=1e-9)
        for _ in range(T):
            net   = X @ W64
            dot   = (X * net).sum(-1, keepdim=True)
            F_tan = K * (net - dot * X)
            X     = F.normalize(X + dt * F_tan, p=2, dim=-1, eps=1e-9)
        overlaps = X @ P64.T
        affinity = F.softmax(overlaps / 0.1, dim=-1)
        return -(affinity * torch.log(affinity + 1e-9)).sum(-1)  # (B, N)

    weight = router.proj.weight.detach().double().requires_grad_(True)
    E      = torch.randn(1, 3, 8, dtype=torch.float64, requires_grad=True)

    ok = gradcheck(soft_forward, (weight, E), eps=1e-5, atol=1e-4, rtol=1e-3)
    assert ok, "gradcheck failed: analytic and finite-difference gradients diverge"
    print("[PASS] Numerical gradcheck passed (analytic ≈ finite-difference)")


if __name__ == "__main__":
    print("-- Gradient Flow Verification --\n")
    check_projection_gradient()
    check_buffer_isolation()
    check_numerical_gradcheck()
    print("\n[OK] All gradient checks passed.")

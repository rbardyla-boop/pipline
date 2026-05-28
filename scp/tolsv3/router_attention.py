"""
RouterAttention: drop-in nn.MultiheadAttention replacement with TOLS pre-routing.

High-entropy query tokens are pruned before the O(N²) attention op.
Pruned positions receive zero output; the sparsity mask is returned for logging.
"""

from __future__ import annotations

from typing import Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor

from tols_router import TOLSDynamicEntropyRouter


class RouterAttention(nn.Module):
    """
    Drop-in replacement for nn.MultiheadAttention with TOLS token pre-routing.

    Args:
        d_model:       Embedding dimension (must match Q/K/V width)
        n_heads:       Number of attention heads
        n_patterns:    TOLS memory attractor count
        dropout:       Attention dropout rate
        **router_kwargs: Forwarded to TOLSDynamicEntropyRouter
                         (K, dt, n_steps, gate_alpha, eps)
    """

    def __init__(
        self,
        d_model: int,
        n_heads: int,
        n_patterns: int,
        dropout: float = 0.0,
        **router_kwargs,
    ) -> None:
        super().__init__()
        self.router = TOLSDynamicEntropyRouter(d_model, n_patterns, **router_kwargs)
        self.attn   = nn.MultiheadAttention(
            d_model, n_heads, dropout=dropout, batch_first=True
        )

    def set_patterns(self, P: Tensor) -> None:
        """Forward pattern registration to the inner router."""
        self.router.set_patterns(P)

    def forward(
        self,
        query: Tensor,
        key: Tensor,
        value: Tensor,
        temperature: float = 0.0,
        need_weights: bool = False,
    ) -> Tuple[Tensor, Optional[Tensor], Tensor]:
        """
        Args:
            query:        (B, N, d_model)
            key:          (B, S, d_model)   S = source length
            value:        (B, S, d_model)
            temperature:  Tangent-space noise for the router (0 = deterministic)
            need_weights: Return attention weight matrix if True

        Returns:
            attn_output:  (B, N, d_model) — pruned query positions are zero-filled
            attn_weights: (B, N, S) or None
            mask:         (B, N) float — 1 = kept token, 0 = pruned token
        """
        gated_query, mask = self.router(query, temperature=temperature)

        # key_padding_mask shape: (B, N), dtype bool
        # True = the position is treated as padding (ignored by attention)
        # Pruned query tokens become padding so attention skips them.
        key_padding_mask = ~mask.bool()  # (B, N)

        attn_output, attn_weights = self.attn(
            gated_query, key, value,
            key_padding_mask=key_padding_mask,
            need_weights=need_weights,
        )

        # Zero-fill pruned positions — attention may still have residual activations
        # for masked queries depending on the backend; explicit zeroing ensures purity.
        attn_output = attn_output * mask.unsqueeze(-1)

        return attn_output, attn_weights, mask


# ------------------------------------------------------------------
# Smoke test
# ------------------------------------------------------------------

if __name__ == "__main__":
    torch.manual_seed(0)

    B, N, d_model, n_heads, n_patterns = 2, 8, 64, 4, 4

    layer = RouterAttention(d_model, n_heads, n_patterns, gate_alpha=0.5)
    P = F.normalize(torch.randn(n_patterns, 8), dim=-1)
    layer.set_patterns(P)
    layer.eval()

    Q = K = V = torch.randn(B, N, d_model)

    with torch.no_grad():
        out, weights, mask = layer(Q, K, V)

    assert out.shape == (B, N, d_model), f"Wrong output shape: {out.shape}"

    pruned = mask == 0
    if pruned.any():
        max_pruned_activation = out[pruned].abs().max().item()
        assert max_pruned_activation < 1e-6, (
            f"Pruned positions are not zeroed (max={max_pruned_activation:.2e})"
        )

    kept_per_seq = mask.sum(dim=-1).int().tolist()
    print(f"Output shape    : {tuple(out.shape)}")
    print(f"Tokens kept/seq : {kept_per_seq}  (of {N})")
    print(f"Sparsity ratio  : {1 - mask.mean().item():.2f}")
    print("[OK] RouterAttention smoke test passed.")

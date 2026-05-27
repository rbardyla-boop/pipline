"""Minimal Transformer block with pre-norm RMSNorm.

Implements the architecture described in the LLM guide:
  - RMSNorm applied BEFORE attention and feed-forward (pre-norm style)
  - Residual connections around each sub-layer
  - Scaled dot-product attention (single-head, pure Python)
  - SwiGLU-style feed-forward

Structure of one TransformerBlock:
    input x
        │
    ┌───┴──────────────┐  residual
    │       RMSNorm
    │          │
    │       Attention
    │          │
    └──────> (+)
               │
    ┌──────────┴───────┐  residual
    │       RMSNorm
    │          │
    │        FFN
    │          │
    └──────> (+)
               │
             output

Self-igniting: no pre-training, no weight loading. Pure forward-pass math.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from uaf.llm.rms_norm import RMSNorm


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _softmax(scores: list[float]) -> list[float]:
    max_s = max(scores)
    exps = [math.exp(s - max_s) for s in scores]
    total = sum(exps)
    return [e / total for e in exps]


def _relu(x: float) -> float:
    return max(0.0, x)


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _silu(x: float) -> float:
    """SiLU (Swish) activation used in SwiGLU FFN."""
    return x * _sigmoid(x)


@dataclass
class AttentionConfig:
    dim: int
    heads: int = 1
    eps: float = 1e-6


class ScaledDotProductAttention:
    """Single-head scaled dot-product attention.

    Uses identity projections (Q=K=V=input) for a self-contained demo.
    Real LLMs learn separate Q/K/V weight matrices.

    Args:
        dim: Hidden dimension.
        scale: Scale factor (default = 1/sqrt(dim)).
    """

    def __init__(self, dim: int, scale: float | None = None) -> None:
        self._dim = dim
        self._scale = scale or (1.0 / math.sqrt(dim))

    def forward(
        self,
        query: list[list[float]],
        key: list[list[float]],
        value: list[list[float]],
    ) -> list[list[float]]:
        """Compute attention over sequences of vectors.

        Args:
            query: List of T_q vectors of size dim.
            key:   List of T_k vectors of size dim.
            value: List of T_k vectors of size dim.

        Returns:
            List of T_q output vectors of size dim.
        """
        T_q = len(query)
        T_k = len(key)
        outputs = []

        for q in query:
            # Compute scaled scores against all keys
            scores = [_dot(q, k) * self._scale for k in key]
            weights = _softmax(scores)
            # Weighted sum of values
            out = [sum(weights[j] * value[j][i] for j in range(T_k)) for i in range(self._dim)]
            outputs.append(out)

        return outputs


class FeedForwardNetwork:
    """Two-layer FFN with SiLU gate (simplified SwiGLU).

    Real LLMs learn W1, W2, W_gate. Here we use fixed identity+scale
    projections so the module is self-contained without learned weights.

    Args:
        dim:    Input/output dimension.
        hidden: Hidden layer size (default = 4 * dim).
    """

    def __init__(self, dim: int, hidden: int | None = None) -> None:
        self._dim = dim
        self._hidden = hidden or (4 * dim)

    def forward(self, x: list[float]) -> list[float]:
        """Apply FFN. Returns a vector of the same size as input."""
        # Expand to hidden dim (identity repeat or truncate for demo)
        h = [x[i % self._dim] for i in range(self._hidden)]
        # Gate: SiLU activation
        gate = [_silu(v) for v in h]
        # Contract back to dim
        out = []
        stride = self._hidden // self._dim if self._hidden >= self._dim else 1
        for d in range(self._dim):
            segment = gate[d * stride: (d + 1) * stride] or [gate[d % len(gate)]]
            out.append(sum(segment) / len(segment))
        return out


class TransformerBlock:
    """One Transformer block with pre-norm RMSNorm + residuals.

    Implements the architecture from the LLM guide:
      x → RMSNorm → Attention → (+x) → RMSNorm → FFN → (+x)

    Args:
        dim: Hidden dimension.
        eps: RMSNorm epsilon.
    """

    def __init__(self, dim: int, eps: float = 1e-6) -> None:
        self._dim = dim
        self._norm1 = RMSNorm(dim, eps)
        self._norm2 = RMSNorm(dim, eps)
        self._attn = ScaledDotProductAttention(dim)
        self._ffn = FeedForwardNetwork(dim)

    def forward(self, sequence: list[list[float]]) -> list[list[float]]:
        """Process a sequence of vectors through one Transformer block.

        Args:
            sequence: List of T vectors, each of size dim.

        Returns:
            List of T output vectors of size dim.
        """
        # Pre-norm attention sublayer
        normed = [self._norm1.forward(x) for x in sequence]
        attn_out = self._attn.forward(normed, normed, normed)
        # Residual
        x1 = [
            [sequence[t][d] + attn_out[t][d] for d in range(self._dim)]
            for t in range(len(sequence))
        ]

        # Pre-norm FFN sublayer
        normed2 = [self._norm2.forward(x) for x in x1]
        ffn_out = [self._ffn.forward(x) for x in normed2]
        # Residual
        x2 = [
            [x1[t][d] + ffn_out[t][d] for d in range(self._dim)]
            for t in range(len(x1))
        ]

        return x2

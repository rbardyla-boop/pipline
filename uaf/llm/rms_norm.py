"""RMSNorm — Root Mean Square Layer Normalization.

As documented in the LLM architecture guide: faster and simpler than
LayerNorm. Powers Llama, Mistral, Gemma, Qwen, PaLM, DeepSeek.

Drops mean subtraction (re-centering) — keeps only re-scaling via RMS.
7-64% faster than LayerNorm in practice. Same accuracy.

Formula:
    RMS(x) = sqrt(mean(x²) + ε)
    RMSNorm(x) = γ * x / RMS(x)

Self-contained: pure Python + math module. No torch, no numpy required.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence


@dataclass
class RMSNorm:
    """Root Mean Square Layer Normalization.

    Args:
        dim: Dimension of the input vectors.
        eps: Stability epsilon to avoid division by zero.
        gamma: Learned scale parameter (defaults to ones).
    """

    dim: int
    eps: float = 1e-6
    gamma: list[float] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.gamma:
            self.gamma = [1.0] * self.dim
        if len(self.gamma) != self.dim:
            raise ValueError(
                f"gamma length {len(self.gamma)} != dim {self.dim}"
            )

    def forward(self, x: Sequence[float]) -> list[float]:
        """Apply RMSNorm to vector *x*.

        Args:
            x: Input vector of length dim.

        Returns:
            Normalized vector of the same length.
        """
        if len(x) != self.dim:
            raise ValueError(f"Input length {len(x)} != dim {self.dim}")

        rms = self._rms(x)
        return [self.gamma[i] * xi / rms for i, xi in enumerate(x)]

    def rms(self, x: Sequence[float]) -> float:
        """Return the RMS value of *x* (without applying normalization)."""
        return self._rms(x)

    def _rms(self, x: Sequence[float]) -> float:
        mean_sq = sum(xi * xi for xi in x) / len(x)
        return math.sqrt(mean_sq + self.eps)

    @classmethod
    def layernorm_baseline(
        cls, x: Sequence[float], eps: float = 1e-6
    ) -> list[float]:
        """LayerNorm for comparison — has both re-centering and re-scaling."""
        n = len(x)
        mean = sum(x) / n
        centered = [xi - mean for xi in x]
        var = sum(c * c for c in centered) / n
        std = math.sqrt(var + eps)
        return [c / std for c in centered]

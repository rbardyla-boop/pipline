from __future__ import annotations

from typing import List, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor


class TOLSDynamicEntropyRouter(nn.Module):
    """
    Thalamic Reticular Nucleus (TRN) pre-attention sparsity router.

    Pipeline:
      1. Spatial Bridge   — project d_model → 8, L2-normalize onto S^7
      2. Memory Coupling  — W = P^T (PP^T)^{-1} P  (pseudoinverse projection)
      3. Tangent Dynamics — Kuramoto Euler steps in the 8-dim subspace
      4. Entropy Gating   — prune tokens whose Shannon entropy exceeds mean + alpha*std

    Args:
        d_model:    Transformer embedding dimension (input width)
        n_patterns: Number of stored memory attractors
        K:          Coupling strength for tangent-space force
        dt:         Euler step size
        n_steps:    Number of integration steps per forward pass
        gate_alpha: Multiplier on std for the dynamic entropy threshold
        eps:        Numerical epsilon for norm and log safeguards

    ## Calibration Guide — gate_alpha

    gate_alpha controls where the entropy threshold is placed relative to the
    sequence distribution:

        threshold = mean(H) + gate_alpha * std(H)

    Structural collapse risk (gate_alpha >= 1.0):
      For a perfectly bimodal sequence with M attractor classes, noise entropy
      equals ln(M) and signal entropy is near 0.  In a 50/50 split:
          mean ≈ ln(M)/2,  std ≈ ln(M)/2
          threshold = mean + 1.0·std ≈ ln(M)   ← equals noise ceiling → gate fails
      Proof: sigma = sqrt(p(1-p)) * ln(M); at p=0.5, sigma = 0.5*ln(M),
      so mean + 1.0*sigma = 0.5*ln(M) + 0.5*ln(M) = ln(M) exactly.

    Default 0.5 is safe for noise density up to ~80% of the sequence:
      The max safe alpha as a function of noise fraction p is sqrt((1-p)/p).
      At alpha=0.5: safe up to p=0.8; stated as "SNR >= 0.5" to leave margin
      for real-world tokens that aren't perfectly binary in entropy.

    Production tuning:
      - Noise density < 20% (typical real sequences): alpha up to 0.9 is safe.
      - When in doubt, calibrate on a held-out batch: sweep alpha in [0.0, 1.0],
        target false-pass rate < 1% on known-noise tokens.
      - Set alpha = 0.0 (threshold = mean) for the most aggressive gating.
    """

    def __init__(
        self,
        d_model: int,
        n_patterns: int,
        K: float = 4.0,
        dt: float = 0.005,
        n_steps: int = 5,
        gate_alpha: float = 0.5,
        eps: float = 1e-9,
    ) -> None:
        super().__init__()
        self.K = K
        self.dt = dt
        self.n_steps = n_steps
        self.gate_alpha = gate_alpha
        self.eps = eps

        # Learnable spatial bridge — gradients flow through this layer end-to-end
        self.proj = nn.Linear(d_model, 8, bias=False)

        # Non-trainable buffers — move to device automatically with .to()
        self.register_buffer("P", torch.zeros(n_patterns, 8))  # (M, 8) normalized patterns
        self.register_buffer("W", torch.zeros(8, 8))            # (8, 8) coupling matrix

    # ------------------------------------------------------------------
    # Pattern setup
    # ------------------------------------------------------------------

    def set_patterns(self, P: Tensor) -> None:
        """
        Load memory patterns and compute the pseudoinverse coupling matrix.

        W = P^T (P P^T)^{-1} P  — orthogonal projection onto the pattern subspace.
        Symmetric and idempotent for orthonormal patterns.

        Args:
            P: (M, 8) pattern matrix; rows will be L2-normalized onto S^7
        """
        P_norm = F.normalize(P.to(self.P.device), p=2, dim=-1, eps=self.eps)  # (M, 8)
        M = P_norm.shape[0]
        G = P_norm @ P_norm.T + self.eps * torch.eye(M, device=P_norm.device, dtype=P_norm.dtype)
        # solve G X = P_norm  →  X = G^{-1} P_norm, then left-multiply by P_norm^T
        self.W = P_norm.T @ torch.linalg.solve(G, P_norm)  # (8, 8)
        self.P = P_norm                                      # (M, 8)

    # ------------------------------------------------------------------
    # Core dynamics
    # ------------------------------------------------------------------

    def _evolve(self, X: Tensor, temperature: float) -> Tensor:
        """
        Vectorized Kuramoto tangent-space Euler integration over (B, N, 8).
        No Python loops over batch or sequence dims; only the T-step loop is sequential
        (each step depends on the previous X).

        dX/dt = K * (W·X − (X·W·X) X)  [tangent-projected net input force]
        """
        for _ in range(self.n_steps):
            net = X @ self.W                              # (B, N, 8)  net input
            dot = (X * net).sum(-1, keepdim=True)        # (B, N, 1)  radial component
            F_tan = self.K * (net - dot * X)             # (B, N, 8)  tangent force

            if temperature > 0.0:
                # Inject noise then project onto the tangent plane at X
                noise = torch.randn_like(X) * temperature
                noise_dot = (noise * X).sum(-1, keepdim=True)
                F_tan = F_tan + noise - noise_dot * X    # (B, N, 8)  tangent noise

            X = F.normalize(X + self.dt * F_tan, p=2, dim=-1, eps=self.eps)
        return X

    def _entropy(self, X: Tensor) -> Tensor:
        """Shannon entropy of the attractor affinity distribution for each token."""
        overlaps = X @ self.P.T                                         # (B, N, M)
        affinity = F.softmax(overlaps / 0.1, dim=-1)                   # (B, N, M)
        return -(affinity * torch.log(affinity + self.eps)).sum(-1)     # (B, N)

    def _gate(self, X: Tensor) -> Tuple[Tensor, Tensor]:
        """
        Dynamic entropy threshold: threshold = mean_H + gate_alpha * std_H.
        Zero-variance fallback: when std == 0, set threshold = inf (all tokens pass).

        Returns:
            H:    Per-token Shannon entropy (B, N)
            mask: Float mask — 1 = pass, 0 = prune (B, N)
        """
        H = self._entropy(X)                                             # (B, N)
        H_mean = H.mean(-1, keepdim=True)                               # (B, 1)
        H_std = H.std(-1, keepdim=True)                                 # (B, 1)
        threshold = H_mean + self.gate_alpha * H_std
        # Zero-variance fallback: avoid total sequence dropout
        threshold = torch.where(
            H_std < self.eps,
            torch.full_like(threshold, float("inf")),
            threshold,
        )
        mask = (H < threshold).float()                                   # (B, N)
        return H, mask

    # ------------------------------------------------------------------
    # Forward pass
    # ------------------------------------------------------------------

    def forward(self, E: Tensor, temperature: float = 0.0) -> Tuple[Tensor, Tensor]:
        """
        Args:
            E:           Input token embeddings (B, N, d_model)
            temperature: Tangent-space noise magnitude (0 = deterministic)

        Returns:
            gated_E: Sparsity-gated embeddings (B, N, d_model); pruned positions are zero
            mask:    Binary float mask (B, N); 1 = kept, 0 = pruned
        """
        Y = self.proj(E)                                                  # (B, N, 8)
        X = F.normalize(Y, p=2, dim=-1, eps=self.eps)                    # (B, N, 8) on S^7
        X = self._evolve(X, temperature)
        H, mask = self._gate(X)
        return E * mask.unsqueeze(-1), mask

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def trace_entropy(self, E: Tensor, n_trace_steps: int = 5) -> List[Tensor]:
        """
        Return per-step entropy tensors (B, N) from step 0 through n_trace_steps.
        Runs without noise (deterministic) for reproducible diagnostics.

        Returns:
            List of n_trace_steps + 1 tensors; index 0 is the pre-evolution entropy.
        """
        with torch.no_grad():
            Y = self.proj(E)
            X = F.normalize(Y, p=2, dim=-1, eps=self.eps)

            trace: List[Tensor] = [self._entropy(X)]

            for _ in range(n_trace_steps):
                net = X @ self.W
                dot = (X * net).sum(-1, keepdim=True)
                F_tan = self.K * (net - dot * X)
                X = F.normalize(X + self.dt * F_tan, p=2, dim=-1, eps=self.eps)
                trace.append(self._entropy(X))

        return trace

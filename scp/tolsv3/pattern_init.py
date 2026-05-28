"""
Data-driven pattern initialization for TOLSDynamicEntropyRouter.

fit_patterns() extracts memory attractors from training data via K-Means
clustering in the 8-dim projected subspace on S^7.

warm_start_patterns() is a convenience wrapper for HuggingFace-style pipelines.
Requires: transformers (pip install transformers) for warm_start_patterns only.
"""

from __future__ import annotations

from typing import Iterable, Optional

import torch
import torch.nn.functional as F
from torch import Tensor

from tols_router import TOLSDynamicEntropyRouter


def fit_patterns(
    router: TOLSDynamicEntropyRouter,
    dataloader: Iterable,
    n_patterns: int,
    device: Optional[torch.device] = None,
    max_samples: int = 50_000,
    kmeans_seed: int = 42,
) -> Tensor:
    """
    Learn memory patterns from training embeddings via K-Means on S^7.

    Algorithm:
      1. Project each batch through router.proj (no grad) → (N_total, 8)
      2. L2-normalize every point onto S^7
      3. K-Means in R^8 (centroids in the interior, pulled back to sphere)
      4. L2-normalize centroids → n_patterns unit vectors on S^7
      5. Call router.set_patterns(centroids) and return centroids

    Args:
        router:       Router whose proj layer defines the 8-dim subspace
        dataloader:   Iterable of (B, N, d_model) or (B, d_model) tensors
        n_patterns:   Number of attractor clusters (== n_patterns used at construction)
        device:       Target device; defaults to router.proj.weight.device
        max_samples:  Cap on total token count collected before fitting
        kmeans_seed:  sklearn KMeans random_state for reproducibility

    Returns:
        centroids: (n_patterns, 8) Tensor of L2-normalized cluster centers
    """
    from sklearn.cluster import KMeans  # deferred: only needed here

    if device is None:
        device = router.proj.weight.device

    router.eval()
    collected: list[Tensor] = []
    total = 0

    with torch.no_grad():
        for batch in dataloader:
            if isinstance(batch, (list, tuple)):
                batch = batch[0]
            batch = batch.to(device)

            # Accept (B, N, d_model) or (B, d_model)
            if batch.dim() == 2:
                batch = batch.unsqueeze(0)

            Y = router.proj(batch)                              # (B, N, 8)
            X = F.normalize(Y, p=2, dim=-1, eps=router.eps)    # (B, N, 8) on S^7
            flat = X.reshape(-1, 8).cpu()                       # (B*N, 8)
            collected.append(flat)
            total += flat.shape[0]
            if total >= max_samples:
                break

    embeddings = torch.cat(collected, dim=0)[:max_samples].numpy()  # (N_total, 8)

    km = KMeans(n_clusters=n_patterns, random_state=kmeans_seed, n_init="auto")
    km.fit(embeddings)

    centroids = torch.from_numpy(km.cluster_centers_).float().to(device)  # (M, 8)
    centroids = F.normalize(centroids, p=2, dim=-1, eps=router.eps)
    router.set_patterns(centroids)
    return centroids


def warm_start_patterns(
    router: TOLSDynamicEntropyRouter,
    seed_texts: list[str],
    tokenizer,
    base_model,
    n_patterns: int,
    device: Optional[torch.device] = None,
    layer_idx: int = -1,
    kmeans_seed: int = 42,
) -> Tensor:
    """
    Initialize patterns from a HuggingFace language model's hidden states.

    Extracts hidden states from base_model for each seed_text, concatenates
    them into a single embedding matrix, then calls fit_patterns().

    Args:
        router:      Router to initialize
        seed_texts:  List of representative strings (e.g., domain corpus samples)
        tokenizer:   HuggingFace tokenizer compatible with base_model
        base_model:  HuggingFace model with output_hidden_states support
        n_patterns:  Number of attractor clusters
        device:      Target device; defaults to base_model parameter device
        layer_idx:   Which hidden layer to extract (-1 = last)
        kmeans_seed: Passed to fit_patterns

    Returns:
        centroids: (n_patterns, 8) Tensor of fitted patterns

    Requires:
        pip install transformers
    """
    if device is None:
        device = next(base_model.parameters()).device

    base_model.eval()
    all_hidden: list[Tensor] = []

    with torch.no_grad():
        for text in seed_texts:
            inputs  = tokenizer(text, return_tensors="pt", truncation=True).to(device)
            outputs = base_model(**inputs, output_hidden_states=True)
            # hidden_states: tuple of (1, seq_len, d_model) tensors
            hidden = outputs.hidden_states[layer_idx]  # (1, N, d_model)
            all_hidden.append(hidden.squeeze(0))       # (N, d_model)

    E_all = torch.cat(all_hidden, dim=0).unsqueeze(0)  # (1, N_total, d_model)

    class _SingleBatch:
        def __iter__(self):
            yield E_all

    return fit_patterns(router, _SingleBatch(), n_patterns, device, kmeans_seed=kmeans_seed)


# ------------------------------------------------------------------
# Smoke test
# ------------------------------------------------------------------

if __name__ == "__main__":
    torch.manual_seed(0)

    d_model, n_patterns = 32, 4
    router = TOLSDynamicEntropyRouter(d_model=d_model, n_patterns=n_patterns)

    # Synthetic dataloader: 10 batches of (2, 16, d_model)
    def fake_loader():
        for _ in range(10):
            yield torch.randn(2, 16, d_model)

    centroids = fit_patterns(router, fake_loader(), n_patterns, max_samples=1000)

    assert centroids.shape == (n_patterns, 8), f"Bad centroid shape: {centroids.shape}"
    norms = centroids.norm(dim=-1)
    assert (norms - 1.0).abs().max() < 1e-5, "Centroids not on unit sphere"

    print(f"Centroids shape : {tuple(centroids.shape)}")
    print(f"Max norm error  : {(norms - 1.0).abs().max().item():.2e}")
    print("[OK] fit_patterns smoke test passed.")

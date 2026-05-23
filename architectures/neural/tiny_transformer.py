"""Decoder-only transformer (nano-GPT pattern) in PyTorch.

Configurable via TransformerConfig. Designed to plug directly into
NeuralTransformerCognition as the trainable backbone.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import torch
import torch.nn as nn
import torch.nn.functional as F


@dataclass
class TransformerConfig:
    n_layers: int = 2
    n_heads: int = 4
    embed_dim: int = 64
    context_len: int = 64
    dropout: float = 0.1
    vocab_size: int = 70

    def __post_init__(self) -> None:
        if self.embed_dim % self.n_heads != 0:
            raise ValueError(
                f"embed_dim ({self.embed_dim}) must be divisible by n_heads ({self.n_heads})"
            )


class CausalSelfAttention(nn.Module):
    def __init__(self, cfg: TransformerConfig) -> None:
        super().__init__()
        self.n_heads = cfg.n_heads
        self.head_dim = cfg.embed_dim // cfg.n_heads
        self.qkv = nn.Linear(cfg.embed_dim, 3 * cfg.embed_dim, bias=False)
        self.proj = nn.Linear(cfg.embed_dim, cfg.embed_dim, bias=False)
        self.attn_drop = nn.Dropout(cfg.dropout)
        self.resid_drop = nn.Dropout(cfg.dropout)
        self.register_buffer(
            "mask",
            torch.tril(torch.ones(cfg.context_len, cfg.context_len)).view(
                1, 1, cfg.context_len, cfg.context_len
            ),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        B, T, C = x.shape
        qkv = self.qkv(x).chunk(3, dim=-1)
        q, k, v = (t.view(B, T, self.n_heads, self.head_dim).transpose(1, 2) for t in qkv)
        scale = 1.0 / math.sqrt(self.head_dim)
        att = (q @ k.transpose(-2, -1)) * scale
        att = att.masked_fill(self.mask[:, :, :T, :T] == 0, float("-inf"))
        att = F.softmax(att, dim=-1)
        att = self.attn_drop(att)
        y = att @ v
        y = y.transpose(1, 2).contiguous().view(B, T, C)
        return self.resid_drop(self.proj(y))


class FeedForward(nn.Module):
    def __init__(self, cfg: TransformerConfig) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(cfg.embed_dim, 4 * cfg.embed_dim),
            nn.GELU(),
            nn.Linear(4 * cfg.embed_dim, cfg.embed_dim),
            nn.Dropout(cfg.dropout),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class TransformerBlock(nn.Module):
    def __init__(self, cfg: TransformerConfig) -> None:
        super().__init__()
        self.ln1 = nn.LayerNorm(cfg.embed_dim)
        self.attn = CausalSelfAttention(cfg)
        self.ln2 = nn.LayerNorm(cfg.embed_dim)
        self.ff = FeedForward(cfg)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x + self.attn(self.ln1(x))
        x = x + self.ff(self.ln2(x))
        return x


class TinyTransformer(nn.Module):
    def __init__(self, cfg: TransformerConfig) -> None:
        super().__init__()
        self.cfg = cfg
        self.tok_emb = nn.Embedding(cfg.vocab_size, cfg.embed_dim)
        self.pos_emb = nn.Embedding(cfg.context_len, cfg.embed_dim)
        self.drop = nn.Dropout(cfg.dropout)
        self.blocks = nn.ModuleList([TransformerBlock(cfg) for _ in range(cfg.n_layers)])
        self.ln_f = nn.LayerNorm(cfg.embed_dim)
        self.head = nn.Linear(cfg.embed_dim, cfg.vocab_size, bias=False)
        self.tok_emb.weight = self.head.weight  # weight tying
        self.apply(self._init_weights)

    @staticmethod
    def _init_weights(module: nn.Module) -> None:
        if isinstance(module, nn.Linear):
            nn.init.normal_(module.weight, mean=0.0, std=0.02)
            if module.bias is not None:
                nn.init.zeros_(module.bias)
        elif isinstance(module, nn.Embedding):
            nn.init.normal_(module.weight, mean=0.0, std=0.02)

    def forward(self, idx: torch.Tensor) -> torch.Tensor:
        """Return logits of shape (B, T, vocab_size)."""
        B, T = idx.shape
        assert T <= self.cfg.context_len, f"Sequence length {T} > context_len {self.cfg.context_len}"
        pos = torch.arange(T, device=idx.device).unsqueeze(0)
        x = self.drop(self.tok_emb(idx) + self.pos_emb(pos))
        for block in self.blocks:
            x = block(x)
        x = self.ln_f(x)
        return self.head(x)

    def get_last_hidden_state(self, idx: torch.Tensor) -> torch.Tensor:
        """Return final layer hidden states of shape (B, T, embed_dim)."""
        B, T = idx.shape
        pos = torch.arange(T, device=idx.device).unsqueeze(0)
        x = self.drop(self.tok_emb(idx) + self.pos_emb(pos))
        for block in self.blocks:
            x = block(x)
        return self.ln_f(x)

    @torch.no_grad()
    def generate(self, idx: torch.Tensor, max_new_tokens: int, temperature: float = 1.0) -> torch.Tensor:
        """Autoregressive generation. Returns extended token sequence."""
        for _ in range(max_new_tokens):
            ctx = idx[:, -self.cfg.context_len:]
            logits = self(ctx)
            logits = logits[:, -1, :] / temperature
            probs = F.softmax(logits, dim=-1)
            next_tok = torch.multinomial(probs, num_samples=1)
            idx = torch.cat([idx, next_tok], dim=1)
        return idx

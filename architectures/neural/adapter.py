"""NeuralTransformerCognition — wraps TinyTransformer as a CognitionEngine.

Each propose() call:
  1. Trains n_train_steps gradient steps on the combined corpus (seeds + parent text)
  2. Generates max_gen_tokens new tokens from a random seed prefix
  3. Returns the decoded string

embed() mean-pools last-layer hidden states → 384-dim vector (zero-padded if embed_dim < 384).
coherence() returns exp(-cross_entropy_loss) ∈ (0, 1].
"""

from __future__ import annotations

import math
import random
from typing import Sequence

import torch
import torch.nn.functional as F

from architectures.neural.char_tokenizer import CharTokenizer
from architectures.neural.tiny_transformer import TinyTransformer, TransformerConfig
from uaf.interfaces.cognition import CognitionEngine

_EMBED_OUT_DIM = 384


class NeuralTransformerCognition(CognitionEngine):
    """CognitionEngine backed by a character-level TinyTransformer.

    Args (all via config dict from VariantSpec.params):
        n_layers        int   2      transformer depth
        n_heads         int   4      attention heads (embed_dim must be divisible)
        embed_dim       int   64     model width
        context_len     int   32     max sequence length
        dropout         float 0.1    dropout probability
        n_train_steps   int   10     gradient steps per propose() call
        lr              float 3e-4   AdamW learning rate
        max_gen_tokens  int   64     tokens to generate per propose() call
        temperature     float 1.0    sampling temperature
        seeds           list  []     corpus strings — used to build tokenizer + warm up
    """

    def __init__(self, **kwargs) -> None:
        n_layers: int = int(kwargs.get("n_layers", 2))
        n_heads: int = int(kwargs.get("n_heads", 4))
        embed_dim: int = int(kwargs.get("embed_dim", 64))
        context_len: int = int(kwargs.get("context_len", 32))
        dropout: float = float(kwargs.get("dropout", 0.1))
        self._n_train_steps: int = int(kwargs.get("n_train_steps", 10))
        self._lr: float = float(kwargs.get("lr", 3e-4))
        self._max_gen_tokens: int = int(kwargs.get("max_gen_tokens", 64))
        self._temperature: float = float(kwargs.get("temperature", 1.0))
        seeds: list[str] = list(kwargs.get("seeds", []))

        corpus = " ".join(seeds)
        self._tokenizer = CharTokenizer(corpus)

        cfg = TransformerConfig(
            n_layers=n_layers,
            n_heads=n_heads,
            embed_dim=embed_dim,
            context_len=context_len,
            dropout=dropout,
            vocab_size=self._tokenizer.vocab_size,
        )
        self._cfg = cfg
        self._model = TinyTransformer(cfg)
        self._model.train()
        self._optimizer = torch.optim.AdamW(self._model.parameters(), lr=self._lr)

        self._corpus_ids: list[int] = self._tokenizer.encode(corpus) if corpus else []
        self._last_train_loss: float = float("nan")

        # Architecture ID is stable after construction
        self._arch_id = (
            f"neural_L{n_layers}_H{n_heads}_D{embed_dim}_C{context_len}"
        )

    # ------------------------------------------------------------------ #
    # CognitionEngine interface                                            #
    # ------------------------------------------------------------------ #

    @property
    def architecture_id(self) -> str:
        return self._arch_id

    def propose(self, parent: str, context: str) -> str:
        """Train n_train_steps steps, then generate a new candidate string."""
        train_text = " ".join(filter(None, [self._tokenizer.decode(self._corpus_ids), parent, context]))
        train_ids = self._tokenizer.encode(train_text)

        if len(train_ids) > 1:
            self._last_train_loss = self._train(train_ids)

        return self._generate_text()

    def embed(self, text: str) -> list[float]:
        """Mean-pool last-layer hidden states → 384-dim float list."""
        ids = self._tokenizer.encode(text)
        if not ids:
            return [0.0] * _EMBED_OUT_DIM

        ids = ids[: self._cfg.context_len]
        idx = torch.tensor([ids], dtype=torch.long)

        self._model.eval()
        with torch.no_grad():
            hidden = self._model.get_last_hidden_state(idx)  # (1, T, embed_dim)
        self._model.train()

        pooled = hidden[0].mean(dim=0).tolist()  # (embed_dim,)

        if len(pooled) < _EMBED_OUT_DIM:
            pooled = pooled + [0.0] * (_EMBED_OUT_DIM - len(pooled))
        else:
            pooled = pooled[:_EMBED_OUT_DIM]

        return pooled

    def coherence(self, candidate: str) -> float:
        """Return exp(-cross_entropy_loss) ∈ (0, 1]. Lower perplexity → higher coherence."""
        ids = self._tokenizer.encode(candidate)
        if len(ids) < 2:
            return 0.0

        ids = ids[: self._cfg.context_len + 1]
        x_ids = ids[:-1]
        y_ids = ids[1:]

        idx = torch.tensor([x_ids], dtype=torch.long)
        targets = torch.tensor([y_ids], dtype=torch.long)

        self._model.eval()
        with torch.no_grad():
            logits = self._model(idx)  # (1, T, vocab_size)
            loss = F.cross_entropy(
                logits.view(-1, self._cfg.vocab_size),
                targets.view(-1),
            )
        self._model.train()

        return float(math.exp(-loss.item()))

    def reasoning_trace(self) -> dict:
        return {"last_train_loss": self._last_train_loss}

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #

    def _train(self, ids: list[int]) -> float:
        """Run n_train_steps gradient steps on the token sequence. Returns final loss."""
        ctx = self._cfg.context_len
        total_loss = 0.0
        steps_with_data = 0

        for _ in range(self._n_train_steps):
            if len(ids) < 2:
                break
            max_start = max(1, len(ids) - ctx)
            start = random.randint(0, max_start - 1) if max_start > 1 else 0
            chunk = ids[start : start + ctx + 1]
            if len(chunk) < 2:
                continue

            x = torch.tensor([chunk[:-1]], dtype=torch.long)
            y = torch.tensor([chunk[1:]], dtype=torch.long)

            self._optimizer.zero_grad()
            logits = self._model(x)
            loss = F.cross_entropy(
                logits.view(-1, self._cfg.vocab_size),
                y.view(-1),
            )
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self._model.parameters(), 1.0)
            self._optimizer.step()

            total_loss += loss.item()
            steps_with_data += 1

        return total_loss / steps_with_data if steps_with_data else float("nan")

    def _generate_text(self) -> str:
        """Generate max_gen_tokens tokens from a short seed prefix."""
        if self._corpus_ids:
            prefix_len = min(8, len(self._corpus_ids))
            start = random.randint(0, max(0, len(self._corpus_ids) - prefix_len))
            prefix = self._corpus_ids[start : start + prefix_len]
        else:
            prefix = [1]  # first real token

        idx = torch.tensor([prefix], dtype=torch.long)

        self._model.eval()
        out_ids = self._model.generate(idx, self._max_gen_tokens, temperature=self._temperature)
        self._model.train()

        new_ids = out_ids[0, len(prefix) :].tolist()
        return self._tokenizer.decode(new_ids)

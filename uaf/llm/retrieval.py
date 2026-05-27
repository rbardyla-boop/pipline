"""Lesson 3: Retrieval Is More Important Than Fine-Tuning.

Vector-based RAG pipeline. Works with any embedding function — defaults to
a simple TF-IDF-style cosine on bag-of-words so tests run without GPU or API.

Self-igniting: no pre-loaded corpus required. Add documents, then query.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Sequence


@dataclass(frozen=True)
class Document:
    text: str
    doc_id: str
    metadata: dict = field(default_factory=dict, compare=False)


@dataclass(frozen=True)
class RetrievalResult:
    document: Document
    score: float
    rank: int


def _default_embed(text: str) -> list[float]:
    """Bag-of-words TF-IDF approximation. No external deps."""
    tokens = text.lower().split()
    counts: dict[str, int] = {}
    for t in tokens:
        counts[t] = counts.get(t, 0) + 1
    total = max(1, len(tokens))
    # Use IDF = log(1 + 1/count) as a simple weight
    vec = {t: (c / total) * math.log(1 + 1 / c) for t, c in counts.items()}
    return _sparse_to_dense(vec, tokens)


def _sparse_to_dense(vec: dict[str, float], vocab: list[str]) -> list[float]:
    # Return sorted-key values so same vocab → same index
    keys = sorted(vec.keys())
    return [vec[k] for k in keys]


def _cosine(a: list[float], b_lookup: dict[str, float], a_keys: list[str]) -> float:
    """Cosine similarity using the sparse representation for efficiency."""
    dot = sum(a[i] * b_lookup.get(k, 0.0) for i, k in enumerate(a_keys))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b_lookup.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class RetrievalPipeline:
    """Lightweight in-memory RAG pipeline.

    Args:
        embed_fn:     Embedding function for documents and queries.
        chunk_size:   Max words per chunk (0 = no chunking).
        rerank_fn:    Optional re-ranker: (query, results) → reordered results.
    """

    def __init__(
        self,
        embed_fn: Callable[[str], Sequence[float]] | None = None,
        chunk_size: int = 0,
        rerank_fn: Callable[[str, list[RetrievalResult]], list[RetrievalResult]] | None = None,
    ) -> None:
        self._embed_fn = embed_fn or _default_embed
        self._chunk_size = chunk_size
        self._rerank_fn = rerank_fn
        self._docs: list[Document] = []
        self._embeddings: list[list[float]] = []

    def add(self, document: Document) -> None:
        """Add a document (optionally chunked) to the index."""
        chunks = self._chunk(document)
        for chunk in chunks:
            self._docs.append(chunk)
            self._embeddings.append(list(self._embed_fn(chunk.text)))

    def add_texts(self, texts: list[str]) -> None:
        for i, text in enumerate(texts):
            self.add(Document(text=text, doc_id=f"auto_{i}"))

    def query(self, text: str, top_k: int = 5) -> list[RetrievalResult]:
        """Retrieve top-k most relevant documents."""
        if not self._docs:
            return []

        q_emb = list(self._embed_fn(text))
        q_tokens = text.lower().split()
        q_keys = sorted(set(q_tokens))
        q_sparse = {
            t: q_emb[i] for i, t in enumerate(
                sorted(set(text.lower().split()))
            ) if i < len(q_emb)
        }

        scores: list[tuple[float, int]] = []
        for idx, (doc_emb) in enumerate(self._embeddings):
            doc_text = self._docs[idx].text.lower().split()
            doc_keys = sorted(set(doc_text))
            doc_sparse = {}
            for i, k in enumerate(doc_keys):
                if i < len(doc_emb):
                    doc_sparse[k] = doc_emb[i]

            score = _cosine(
                [q_sparse.get(k, 0.0) for k in q_keys],
                doc_sparse,
                q_keys,
            )
            scores.append((score, idx))

        scores.sort(key=lambda x: x[0], reverse=True)
        top = scores[: top_k]

        results = [
            RetrievalResult(document=self._docs[idx], score=sc, rank=rank + 1)
            for rank, (sc, idx) in enumerate(top)
        ]

        if self._rerank_fn:
            results = self._rerank_fn(text, results)

        return results

    def size(self) -> int:
        return len(self._docs)

    def _chunk(self, doc: Document) -> list[Document]:
        if self._chunk_size <= 0:
            return [doc]
        words = doc.text.split()
        if len(words) <= self._chunk_size:
            return [doc]
        chunks = []
        for i, start in enumerate(range(0, len(words), self._chunk_size)):
            chunk_text = " ".join(words[start: start + self._chunk_size])
            chunks.append(Document(
                text=chunk_text,
                doc_id=f"{doc.doc_id}_chunk{i}",
                metadata={**doc.metadata, "chunk": i, "parent_id": doc.doc_id},
            ))
        return chunks

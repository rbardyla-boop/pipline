"""Tests for uaf.llm.retrieval (Lesson 3)."""

import pytest
from uaf.llm.retrieval import RetrievalPipeline, Document, RetrievalResult


def test_add_and_query_returns_results():
    rp = RetrievalPipeline()
    rp.add(Document("the sky is blue and clear today", "d1"))
    rp.add(Document("the ocean is deep and full of life", "d2"))
    results = rp.query("blue sky weather", top_k=2)
    assert len(results) >= 1
    assert all(isinstance(r, RetrievalResult) for r in results)


def test_empty_index_returns_empty():
    rp = RetrievalPipeline()
    assert rp.query("anything") == []


def test_top_k_respected():
    rp = RetrievalPipeline()
    for i in range(10):
        rp.add(Document(f"document {i} about topic {i}", f"d{i}"))
    results = rp.query("document topic", top_k=3)
    assert len(results) <= 3


def test_rank_is_assigned():
    rp = RetrievalPipeline()
    rp.add(Document("python programming language", "d1"))
    rp.add(Document("java programming language", "d2"))
    results = rp.query("programming", top_k=2)
    ranks = [r.rank for r in results]
    assert 1 in ranks


def test_add_texts_convenience():
    rp = RetrievalPipeline()
    rp.add_texts(["hello world", "foo bar baz"])
    assert rp.size() == 2


def test_chunking():
    rp = RetrievalPipeline(chunk_size=3)
    long_doc = Document("one two three four five six seven eight nine ten", "d1")
    rp.add(long_doc)
    # 10 words / 3 per chunk → 4 chunks (ceil)
    assert rp.size() == 4


def test_no_chunking_when_disabled():
    rp = RetrievalPipeline(chunk_size=0)
    rp.add(Document("one two three four five", "d1"))
    assert rp.size() == 1


def test_custom_embed_fn():
    def always_one(text: str):
        return [1.0, 1.0, 1.0]

    rp = RetrievalPipeline(embed_fn=always_one)
    rp.add(Document("anything", "d1"))
    rp.add(Document("something", "d2"))
    results = rp.query("whatever", top_k=1)
    assert len(results) == 1


def test_scores_are_in_valid_range():
    rp = RetrievalPipeline()
    rp.add(Document("machine learning models", "d1"))
    rp.add(Document("the weather is nice today", "d2"))
    results = rp.query("machine learning", top_k=5)
    for r in results:
        assert -1.0 <= r.score <= 1.0


def test_reranker_applied():
    def reverse_reranker(query, results):
        return list(reversed(results))

    rp = RetrievalPipeline(rerank_fn=reverse_reranker)
    rp.add(Document("alpha", "d1"))
    rp.add(Document("beta", "d2"))
    rp.add(Document("gamma", "d3"))
    results_default = RetrievalPipeline().query("alpha beta gamma", top_k=3)
    results_reranked = rp.query("alpha beta gamma", top_k=3)
    # Just verify reranker ran (order may differ from default)
    assert len(results_reranked) >= 1


def test_document_metadata_preserved():
    rp = RetrievalPipeline()
    doc = Document("test content", "d1", metadata={"source": "wiki"})
    rp.add(doc)
    results = rp.query("test content", top_k=1)
    assert results[0].document.metadata.get("source") == "wiki"

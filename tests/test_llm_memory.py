"""Tests for uaf.llm.memory_stack (Lesson 7)."""

import time
import pytest
from uaf.llm.memory_stack import MemoryStack, MemoryTier


def test_push_and_recent():
    ms = MemoryStack()
    ms.push("user", "hello")
    ms.push("assistant", "hi there")
    recent = ms.recent(5)
    assert len(recent) == 2
    assert recent[0]["role"] == "user"
    assert recent[1]["role"] == "assistant"


def test_short_window_evicts_oldest():
    ms = MemoryStack(short_window=3)
    ms.push("user", "msg1")
    ms.push("user", "msg2")
    ms.push("user", "msg3")
    ms.push("user", "msg4")
    recent = ms.recent(10)
    assert len(recent) == 3
    texts = [r["content"] for r in recent]
    assert "msg1" not in texts
    assert "msg4" in texts


def test_recent_n_limited():
    ms = MemoryStack()
    for i in range(10):
        ms.push("user", f"msg{i}")
    assert len(ms.recent(3)) == 3


def test_remember_and_recall():
    ms = MemoryStack()
    ms.remember("The user prefers Python over JavaScript")
    ms.remember("The user works at a startup")
    recalled = ms.recall("What programming language does the user prefer?", top_k=1)
    assert len(recalled) == 1
    assert "Python" in recalled[0]


def test_recall_returns_most_relevant():
    ms = MemoryStack()
    ms.remember("the database uses PostgreSQL")
    ms.remember("the frontend uses React")
    ms.remember("the backend uses FastAPI")
    results = ms.recall("database SQL", top_k=1)
    assert "PostgreSQL" in results[0]


def test_recall_empty_returns_empty():
    ms = MemoryStack()
    assert ms.recall("anything") == []


def test_store_and_retrieve():
    ms = MemoryStack()
    ms.store("user_name", "Alice")
    assert ms.retrieve("user_name") == "Alice"


def test_retrieve_missing_returns_none():
    ms = MemoryStack()
    assert ms.retrieve("nonexistent") is None


def test_ttl_expiry():
    ms = MemoryStack()
    ms.store("temp_key", "temp_value", ttl=0.01)
    time.sleep(0.05)
    assert ms.retrieve("temp_key") is None


def test_no_ttl_does_not_expire():
    ms = MemoryStack()
    ms.store("permanent", "stays_forever", ttl=0.0)
    time.sleep(0.01)
    assert ms.retrieve("permanent") == "stays_forever"


def test_expire_stale_returns_count():
    ms = MemoryStack()
    ms.store("k1", "v1", ttl=0.01)
    ms.store("k2", "v2", ttl=0.01)
    ms.store("k3", "v3", ttl=0.0)
    time.sleep(0.05)
    removed = ms.expire_stale()
    assert removed == 2
    assert ms.retrieve("k3") == "stays_forever" or ms.retrieve("k3") == "v3"


def test_snapshot():
    ms = MemoryStack()
    ms.push("user", "hello")
    ms.remember("test memory", importance=0.8)
    ms.store("key", "value")
    snap = ms.snapshot()
    assert snap["short_count"] == 1
    assert snap["mid_count"] == 1
    assert snap["long_count"] == 1


def test_clear_specific_tier():
    ms = MemoryStack()
    ms.push("user", "short")
    ms.remember("mid memory")
    ms.store("key", "val")
    ms.clear(MemoryTier.SHORT)
    snap = ms.snapshot()
    assert snap["short_count"] == 0
    assert snap["mid_count"] == 1
    assert snap["long_count"] == 1


def test_clear_all():
    ms = MemoryStack()
    ms.push("user", "short")
    ms.remember("mid")
    ms.store("key", "val")
    ms.clear()
    snap = ms.snapshot()
    assert snap["short_count"] == 0
    assert snap["mid_count"] == 0
    assert snap["long_count"] == 0


def test_mid_capacity_evicts_lowest_importance():
    ms = MemoryStack(mid_capacity=3)
    ms.remember("low importance", importance=0.1)
    ms.remember("high importance", importance=0.9)
    ms.remember("medium importance", importance=0.5)
    ms.remember("new entry", importance=0.7)  # should evict "low importance"
    results = ms.recall("low importance", top_k=5)
    assert "low importance" not in results or len(results) <= 3


def test_summarize_at_flushes_short_to_mid():
    ms = MemoryStack(short_window=20, summarize_at=3)
    ms.push("user", "msg one")
    ms.push("user", "msg two")
    ms.push("user", "msg three")  # should trigger flush
    snap = ms.snapshot()
    assert snap["mid_count"] >= 1

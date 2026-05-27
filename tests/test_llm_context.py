"""Tests for uaf.llm.context_manager (Lesson 2)."""

import pytest
from uaf.llm.context_manager import ContextManager, ContextEntry, ContextPriority


def test_add_single_entry():
    cm = ContextManager(max_tokens=1000)
    added = cm.add("hello world", ContextPriority.HIGH)
    assert added is True
    assert len(cm) == 1
    assert cm.used_tokens() > 0


def test_token_counting_default():
    cm = ContextManager(max_tokens=1000)
    text = "a" * 400  # 400 chars → ~100 tokens
    cm.add(text, ContextPriority.MEDIUM)
    assert 80 <= cm.used_tokens() <= 120


def test_remaining_tokens():
    cm = ContextManager(max_tokens=1000, token_counter=lambda t: 100)
    cm.add("x", ContextPriority.HIGH)
    assert cm.remaining_tokens() == 900


def test_utilization():
    cm = ContextManager(max_tokens=100, token_counter=lambda t: 50)
    cm.add("x", ContextPriority.HIGH)
    assert cm.utilization() == 0.5


def test_budget_enforced_returns_false():
    cm = ContextManager(max_tokens=50, token_counter=lambda t: 100)
    # Single entry exceeds budget after eviction fails
    added = cm.add("big content", ContextPriority.LOW)
    assert added is False
    assert len(cm) == 0


def test_eviction_makes_room():
    cm = ContextManager(max_tokens=100, token_counter=lambda t: 60)
    # Add a low-priority compressible entry
    cm.add("low priority text", ContextPriority.LOW, compressible=True)
    # Now add a higher cost entry — should evict the low one
    added = cm.add("important text", ContextPriority.HIGH)
    assert added is True
    assert len(cm) == 1


def test_non_compressible_entry_not_evicted():
    cm = ContextManager(max_tokens=100, token_counter=lambda t: 60)
    cm.add("critical", ContextPriority.CRITICAL, compressible=False)
    # Try to add another entry — the critical one can't be evicted
    added = cm.add("other", ContextPriority.LOW)
    assert added is False
    assert len(cm) == 1


def test_build_orders_by_priority():
    cm = ContextManager(max_tokens=1000)
    cm.add("low content", ContextPriority.LOW)
    cm.add("critical content", ContextPriority.CRITICAL)
    cm.add("medium content", ContextPriority.MEDIUM)
    result = cm.build()
    # CRITICAL should appear before LOW
    assert result.index("critical") < result.index("low")


def test_clear_tier():
    cm = ContextManager(max_tokens=1000)
    cm.add("ephemeral 1", ContextPriority.EPHEMERAL)
    cm.add("ephemeral 2", ContextPriority.EPHEMERAL)
    cm.add("important", ContextPriority.HIGH)
    freed = cm.clear_tier(ContextPriority.EPHEMERAL)
    assert freed > 0
    assert len(cm) == 1


def test_reset():
    cm = ContextManager(max_tokens=1000)
    cm.add("something", ContextPriority.HIGH)
    cm.reset()
    assert len(cm) == 0
    assert cm.used_tokens() == 0


def test_context_entry_invalid_tokens():
    with pytest.raises(ValueError):
        ContextEntry("text", ContextPriority.HIGH, tokens=-1)


def test_custom_token_counter():
    cm = ContextManager(max_tokens=1000, token_counter=lambda t: len(t))
    cm.add("abc", ContextPriority.MEDIUM)
    assert cm.used_tokens() == 3


def test_multiple_entries_fit():
    cm = ContextManager(max_tokens=1000, token_counter=lambda t: 100)
    for i in range(9):
        added = cm.add(f"entry {i}", ContextPriority.MEDIUM)
        assert added is True
    assert len(cm) == 9

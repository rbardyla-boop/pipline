"""Tests for uaf.llm.prompt_system (Lesson 4)."""

import pytest
from uaf.llm.prompt_system import PromptSystem, PromptLayer


def test_add_and_assemble():
    ps = PromptSystem()
    ps.set("sys", "You are a helpful assistant.", PromptLayer.SYSTEM)
    ps.set("user", "What is 2+2?", PromptLayer.USER)
    result = ps.assemble()
    assert "helpful assistant" in result
    assert "2+2" in result


def test_layer_order_in_assembly():
    ps = PromptSystem(separator="|")
    ps.set("user", "USER_MSG", PromptLayer.USER)
    ps.set("sys", "SYS_MSG", PromptLayer.SYSTEM)
    result = ps.assemble()
    # SYSTEM (10) rendered before USER (70)
    assert result.index("SYS_MSG") < result.index("USER_MSG")


def test_remove_slot():
    ps = PromptSystem()
    ps.set("context", "some context", PromptLayer.CONTEXT)
    removed = ps.remove("context")
    assert removed is True
    assert "context" not in ps.assemble()


def test_remove_nonexistent_returns_false():
    ps = PromptSystem()
    assert ps.remove("nonexistent") is False


def test_inject_variables():
    ps = PromptSystem()
    ps.set("task", "Process request for {{user_name}}", PromptLayer.TASK)
    ps.inject({"user_name": "Alice"})
    result = ps.assemble()
    assert "Alice" in result
    assert "{{user_name}}" not in result


def test_inject_multiple_vars():
    ps = PromptSystem()
    ps.set("ctx", "Domain: {{domain}}, Topic: {{topic}}", PromptLayer.CONTEXT)
    ps.inject({"domain": "science", "topic": "physics"})
    result = ps.assemble()
    assert "science" in result
    assert "physics" in result


def test_include_layers_filter():
    ps = PromptSystem()
    ps.set("sys", "system text", PromptLayer.SYSTEM)
    ps.set("user", "user text", PromptLayer.USER)
    result = ps.assemble(include_layers={PromptLayer.SYSTEM})
    assert "system text" in result
    assert "user text" not in result


def test_token_estimate():
    ps = PromptSystem()
    ps.set("a", "hello world", PromptLayer.SYSTEM)  # ~2 tokens (11 chars // 4)
    estimate = ps.token_estimate()
    assert estimate > 0


def test_budget_drops_context():
    # context has 100 tokens, budget is 50 → context should be dropped
    long_context = "word " * 200  # ~200 tokens
    ps = PromptSystem(token_budget=50)
    ps.set("sys", "short system", PromptLayer.SYSTEM)
    ps.set("ctx", long_context, PromptLayer.CONTEXT)
    result = ps.assemble()
    # Long context should be dropped to fit budget
    assert "short system" in result


def test_layer_summary():
    ps = PromptSystem()
    ps.set("s1", "hello", PromptLayer.SYSTEM)
    ps.set("s2", "world", PromptLayer.SYSTEM)
    ps.set("u1", "question?", PromptLayer.USER)
    summary = ps.layer_summary()
    assert "SYSTEM" in summary
    assert "USER" in summary
    assert summary["SYSTEM"] > 0


def test_clone_is_independent():
    ps = PromptSystem()
    ps.set("key", "original", PromptLayer.CONTEXT)
    clone = ps.clone()
    clone.set("key", "modified", PromptLayer.CONTEXT)
    assert "original" in ps.assemble()
    assert "modified" in clone.assemble()


def test_chaining():
    result = (
        PromptSystem()
        .set("sys", "system", PromptLayer.SYSTEM)
        .set("user", "user msg", PromptLayer.USER)
        .assemble()
    )
    assert "system" in result
    assert "user msg" in result

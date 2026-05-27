"""Tests for uaf.llm.multi_agent (Lesson 10)."""

import pytest
from uaf.llm.multi_agent import AgentRegistry, AgentSpec, AgentResult


def _make_registry():
    registry = AgentRegistry()
    registry.register(
        AgentSpec("researcher", frozenset(["research", "search"]), priority=1),
        lambda q: f"Research: {q}",
    )
    registry.register(
        AgentSpec("planner", frozenset(["plan", "strategy"]), priority=2),
        lambda q: f"Plan: {q}",
    )
    registry.register(
        AgentSpec("coder", frozenset(["code", "implement"]), priority=1),
        lambda q: f"Code: {q}",
    )
    return registry


def test_dispatch_returns_result():
    registry = _make_registry()
    result = registry.dispatch("find papers on LLMs", "research")
    assert isinstance(result, AgentResult)
    assert result.success is True


def test_dispatch_routes_to_correct_agent():
    registry = _make_registry()
    result = registry.dispatch("write a function", "code")
    assert result.agent_id == "coder"


def test_dispatch_no_capability_uses_highest_priority():
    registry = _make_registry()
    result = registry.dispatch("do something")
    # planner has priority=2, which is highest
    assert result.agent_id == "planner"


def test_dispatch_missing_capability_uses_fallback():
    registry = AgentRegistry(fallback_fn=lambda q: "fallback response")
    result = registry.dispatch("unknown query", "unknown_cap")
    assert result.agent_id == "fallback"
    assert result.success is True
    assert result.result == "fallback response"


def test_dispatch_no_fallback_returns_failure():
    registry = AgentRegistry()
    result = registry.dispatch("query", "nonexistent")
    assert result.success is False
    assert "No agent found" in result.error


def test_run_all_returns_multiple_results():
    registry = _make_registry()
    # "research" and "search" match researcher
    results = registry.run_all("search for data", "research")
    assert len(results) == 1
    assert results[0].agent_id == "researcher"


def test_run_all_stop_on_first_success():
    registry = AgentRegistry()
    call_order = []

    def make_handler(name, succeeds):
        def handler(q):
            call_order.append(name)
            if not succeeds:
                raise ValueError(f"{name} failed")
            return f"{name} result"
        return handler

    registry.register(AgentSpec("a1", frozenset(["task"]), priority=3), make_handler("a1", True))
    registry.register(AgentSpec("a2", frozenset(["task"]), priority=2), make_handler("a2", True))
    results = registry.run_all("do task", "task", stop_on_first_success=True)
    assert len(results) == 1


def test_failing_agent_returns_failure_result():
    registry = AgentRegistry()
    registry.register(
        AgentSpec("bad_agent", frozenset(["task"])),
        lambda q: (_ for _ in ()).throw(RuntimeError("broken")),
    )
    result = registry.dispatch("query", "task")
    assert result.success is False
    assert "broken" in result.error


def test_failure_does_not_affect_other_agents():
    registry = AgentRegistry()
    registry.register(
        AgentSpec("good", frozenset(["task"]), priority=1),
        lambda q: "good result",
    )
    registry.register(
        AgentSpec("bad", frozenset(["task"]), priority=0),
        lambda q: (_ for _ in ()).throw(RuntimeError("fails")),
    )
    # dispatch picks highest priority = "good"
    result = registry.dispatch("query", "task")
    assert result.success is True
    assert result.result == "good result"


def test_capabilities_returns_all_tags():
    registry = _make_registry()
    caps = registry.capabilities()
    assert "research" in caps
    assert "code" in caps
    assert "plan" in caps


def test_agent_ids():
    registry = _make_registry()
    ids = registry.agent_ids()
    assert "researcher" in ids
    assert "planner" in ids


def test_unregister():
    registry = _make_registry()
    removed = registry.unregister("researcher")
    assert removed is True
    assert "researcher" not in registry.agent_ids()


def test_unregister_nonexistent_returns_false():
    registry = _make_registry()
    assert registry.unregister("ghost") is False

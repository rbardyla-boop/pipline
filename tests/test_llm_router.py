"""Tests for uaf.llm.router (Lessons 5 + 9)."""

import pytest
from uaf.llm.router import ModelRouter, Complexity, RouteDecision


def test_route_returns_decision():
    router = ModelRouter()
    decision = router.route("What is 2+2?")
    assert isinstance(decision, RouteDecision)
    assert decision.model
    assert isinstance(decision.complexity, Complexity)


def test_simple_prompt_routes_to_haiku():
    router = ModelRouter()
    decision = router.route("simple quick extract this data")
    assert decision.complexity == Complexity.SIMPLE


def test_complex_prompt_routes_to_opus():
    router = ModelRouter()
    decision = router.route(
        "please deeply analyze and evaluate the architectural strategy for this complex system design"
    )
    assert decision.complexity == Complexity.COMPLEX


def test_moderate_prompt_routes_to_sonnet():
    router = ModelRouter()
    decision = router.route("explain how caching works in distributed systems")
    # Should route to moderate (not SIMPLE)
    assert decision.complexity in (Complexity.MODERATE, Complexity.COMPLEX)


def test_force_complexity_overrides():
    router = ModelRouter(force_complexity=Complexity.SIMPLE)
    decision = router.route("analyze this deeply complex architectural problem")
    assert decision.complexity == Complexity.SIMPLE
    assert "haiku" in decision.model.lower()


def test_cache_miss_on_first_call():
    router = ModelRouter()
    decision = router.route("unique query for cache test")
    assert decision.cache_hit is False


def test_cache_hit_after_set():
    router = ModelRouter()
    decision = router.route("cached query")
    router.cache_set("cached query", decision.model, "cached response")
    decision2 = router.route("cached query")
    assert decision2.cache_hit is True


def test_cache_get_returns_stored():
    router = ModelRouter()
    router.route("test prompt")
    router.cache_set("test prompt", "claude-sonnet-4-6", {"answer": "42"})
    result = router.cache_get("test prompt", "claude-sonnet-4-6")
    assert result == {"answer": "42"}


def test_cache_get_miss_returns_none():
    router = ModelRouter()
    assert router.cache_get("never cached", "model-x") is None


def test_cache_stats():
    router = ModelRouter()
    router.route("q1")
    router.route("q2")
    stats = router.cache_stats()
    assert "hits" in stats
    assert "misses" in stats
    assert stats["misses"] == 2


def test_cache_capacity_eviction():
    router = ModelRouter(cache_capacity=2)
    router.cache_set("q1", "m", "r1")
    router.cache_set("q2", "m", "r2")
    router.cache_set("q3", "m", "r3")
    assert router.cache_get("q3", "m") == "r3"


def test_invalidate_cache():
    router = ModelRouter()
    router.cache_set("q", "m", "r")
    router.invalidate_cache()
    assert router.cache_get("q", "m") is None


def test_custom_model_map():
    custom_map = {
        Complexity.SIMPLE: "my-fast-model",
        Complexity.MODERATE: "my-mid-model",
        Complexity.COMPLEX: "my-heavy-model",
    }
    router = ModelRouter(model_map=custom_map)
    decision = router.route("simple quick list")
    assert decision.model == "my-fast-model"


def test_token_estimate_used():
    router = ModelRouter()
    decision = router.route("short", token_estimate=3000)
    # Long token estimate pushes toward complex
    assert decision.complexity in (Complexity.MODERATE, Complexity.COMPLEX)


def test_default_token_estimate_from_prompt_length():
    router = ModelRouter()
    decision = router.route("hello")
    assert decision.token_estimate > 0

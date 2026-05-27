"""Tests for uaf.llm.guardrails (Lesson 6)."""

import pytest
from uaf.llm.guardrails import (
    Guardrails,
    GuardrailsConfig,
    ToolPermission,
    ToolPermissionError,
    RetryExhaustedError,
    HumanCheckpointRequired,
)


def test_successful_action():
    g = Guardrails()
    result = g.run(lambda: 42, "compute")
    assert result == 42


def test_stats_after_success():
    g = Guardrails()
    g.run(lambda: "ok", "action1")
    g.run(lambda: "ok", "action2")
    stats = g.stats()
    assert stats["actions_completed"] == 2


def test_denied_tool_raises():
    cfg = GuardrailsConfig(denied_tools=frozenset(["delete_files"]))
    g = Guardrails(cfg)
    with pytest.raises(ToolPermissionError, match="delete_files"):
        g.check_tool("delete_files")


def test_allowed_tool_passes():
    cfg = GuardrailsConfig(allowed_tools=frozenset(["search", "read"]))
    g = Guardrails(cfg)
    g.check_tool("search")  # should not raise


def test_tool_not_in_allowlist_raises():
    cfg = GuardrailsConfig(allowed_tools=frozenset(["search"]))
    g = Guardrails(cfg)
    with pytest.raises(ToolPermissionError):
        g.check_tool("write_file")


def test_retry_on_failure():
    call_count = {"n": 0}

    def flaky():
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise ValueError("transient error")
        return "success"

    cfg = GuardrailsConfig(max_retries=3, retry_delay_base=0.0)
    g = Guardrails(cfg)
    result = g.run(flaky, "flaky_op")
    assert result == "success"
    assert call_count["n"] == 3


def test_retry_exhausted_raises():
    cfg = GuardrailsConfig(max_retries=2, retry_delay_base=0.0)
    g = Guardrails(cfg)
    with pytest.raises(RetryExhaustedError):
        g.run(lambda: (_ for _ in ()).throw(RuntimeError("always fails")), "bad_op")


def test_cost_budget_enforced():
    cfg = GuardrailsConfig(max_cost_tokens=100)
    g = Guardrails(cfg)
    g.run(lambda: "ok", tokens_estimate=90)
    with pytest.raises(RetryExhaustedError, match="budget"):
        g.run(lambda: "ok", tokens_estimate=20)


def test_human_checkpoint_callback():
    checkpoints = []

    def on_checkpoint(action_name, stats):
        checkpoints.append(action_name)

    cfg = GuardrailsConfig(human_checkpoint_every=2)
    g = Guardrails(cfg, on_human_checkpoint=on_checkpoint)
    g.run(lambda: "a", "first")
    g.run(lambda: "b", "second")
    # After 2 actions, checkpoint fires on 3rd action start
    g.run(lambda: "c", "third")
    assert len(checkpoints) >= 1


def test_human_checkpoint_raises_without_callback():
    cfg = GuardrailsConfig(human_checkpoint_every=1)
    g = Guardrails(cfg)
    g.run(lambda: "first", "first")  # completes (action_count becomes 1)
    with pytest.raises(HumanCheckpointRequired):
        g.run(lambda: "second", "second")  # triggers checkpoint


def test_reset_stats():
    g = Guardrails()
    g.run(lambda: "ok", "x")
    g.reset_stats()
    assert g.stats()["actions_completed"] == 0


def test_action_result_is_passed_through():
    g = Guardrails()
    result = g.run(lambda: {"key": "value"}, "dict_action")
    assert result["key"] == "value"


def test_no_retries_needed_on_success():
    cfg = GuardrailsConfig(max_retries=5, retry_delay_base=0.0)
    g = Guardrails(cfg)
    call_count = {"n": 0}

    def once():
        call_count["n"] += 1
        return "done"

    g.run(once, "once")
    assert call_count["n"] == 1

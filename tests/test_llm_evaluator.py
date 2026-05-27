"""Tests for uaf.llm.evaluator (Lesson 8)."""

import time
import pytest
from uaf.llm.evaluator import Evaluator, EvalMetrics, EvalRecord


def test_record_returns_eval_record():
    ev = Evaluator()
    rec = ev.record("what is 2+2?", "4", latency_ms=10.0)
    assert isinstance(rec, EvalRecord)
    assert rec.prompt == "what is 2+2?"
    assert rec.response == "4"


def test_empty_response_fails():
    ev = Evaluator()
    rec = ev.record("question", "", latency_ms=5.0)
    assert rec.passed is False


def test_non_empty_response_passes():
    ev = Evaluator()
    rec = ev.record("question", "answer", latency_ms=5.0)
    assert rec.passed is True


def test_custom_pass_fn():
    ev = Evaluator(pass_fn=lambda p, r: "correct" in r.lower())
    rec_pass = ev.record("q", "That is correct!", latency_ms=5.0)
    rec_fail = ev.record("q", "I don't know", latency_ms=5.0)
    assert rec_pass.passed is True
    assert rec_fail.passed is False


def test_aggregate_empty_returns_zero():
    ev = Evaluator()
    m = ev.aggregate()
    assert m.count == 0
    assert m.avg_latency_ms == 0.0


def test_aggregate_counts():
    ev = Evaluator()
    ev.record("q1", "a1", latency_ms=10.0)
    ev.record("q2", "a2", latency_ms=20.0)
    m = ev.aggregate()
    assert m.count == 2
    assert m.avg_latency_ms == 15.0


def test_pass_rate():
    ev = Evaluator(pass_fn=lambda p, r: r == "correct")
    ev.record("q", "correct", latency_ms=5.0)
    ev.record("q", "wrong", latency_ms=5.0)
    m = ev.aggregate()
    assert m.pass_rate == 0.5


def test_hallucination_risk_high_certainty():
    ev = Evaluator()
    rec = ev.record(
        "q",
        "It is definitely proven and absolutely guaranteed without doubt.",
        latency_ms=5.0,
    )
    assert rec.hallucination_risk > 0.0


def test_hallucination_risk_hedged_language():
    ev = Evaluator()
    rec_hedged = ev.record(
        "q",
        "I think this might be the answer, possibly.",
        latency_ms=5.0,
    )
    rec_certain = ev.record(
        "q",
        "This is definitely absolutely certain and proven.",
        latency_ms=5.0,
    )
    # Hedged response should have lower risk than certain one
    assert rec_hedged.hallucination_risk <= rec_certain.hallucination_risk


def test_measure_wraps_timing():
    ev = Evaluator()
    rec = ev.measure(lambda: "result", prompt="test")
    assert rec.latency_ms >= 0
    assert rec.response == "result"


def test_regression_check_passes():
    ev = Evaluator()
    baseline = EvalMetrics(
        count=10,
        avg_latency_ms=100.0,
        avg_hallucination_risk=0.5,
        pass_rate=0.8,
    )
    ev.record("q", "ans", latency_ms=90.0)
    checks = ev.regression_check(baseline)
    assert checks["latency_ok"] is True


def test_regression_check_fails_high_latency():
    ev = Evaluator()
    baseline = EvalMetrics(avg_latency_ms=10.0, pass_rate=1.0, avg_hallucination_risk=0.0)
    ev.record("q", "ans", latency_ms=1000.0)
    checks = ev.regression_check(baseline)
    assert checks["latency_ok"] is False


def test_cost_estimate():
    ev = Evaluator(cost_per_1k=2.0)
    ev.record("q", "a", latency_ms=5.0, tokens_used=500)
    cost = ev.cost_estimate()
    assert cost == 1.0  # 500/1000 * 2.0


def test_reset_clears_records():
    ev = Evaluator()
    ev.record("q", "a", latency_ms=5.0)
    ev.reset()
    assert len(ev.records()) == 0
    assert ev.aggregate().count == 0


def test_total_cost_tokens_aggregated():
    ev = Evaluator()
    ev.record("q", "a", latency_ms=5.0, tokens_used=100)
    ev.record("q", "a", latency_ms=5.0, tokens_used=200)
    m = ev.aggregate()
    assert m.total_cost_tokens == 300

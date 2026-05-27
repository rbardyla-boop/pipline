"""Lesson 8: Evaluation Pipelines Are Non-Negotiable.

Most AI builders test manually. That doesn't scale.
This evaluator measures accuracy, hallucination risk, latency, cost,
and consistency without any external API.

Self-igniting: starts recording immediately, no benchmark required.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class EvalMetrics:
    """Aggregate metrics over a set of EvalRecords."""
    count: int = 0
    avg_latency_ms: float = 0.0
    avg_tokens: float = 0.0
    avg_hallucination_risk: float = 0.0
    pass_rate: float = 0.0
    total_cost_tokens: int = 0

    def __repr__(self) -> str:
        return (
            f"EvalMetrics(n={self.count}, "
            f"latency={self.avg_latency_ms:.1f}ms, "
            f"hallucination_risk={self.avg_hallucination_risk:.2f}, "
            f"pass_rate={self.pass_rate:.2f})"
        )


@dataclass
class EvalRecord:
    prompt: str
    response: str
    latency_ms: float
    tokens_used: int
    passed: bool
    hallucination_risk: float
    metadata: dict[str, Any] = field(default_factory=dict)


# Phrases that signal hallucination risk
_CERTAINTY_PATTERNS = [
    "definitely", "certainly", "absolutely", "without doubt",
    "it is a fact", "proven", "guaranteed",
]
_HEDGE_PATTERNS = [
    "i think", "i believe", "might", "could be", "possibly",
    "not sure", "unclear", "may", "perhaps",
]


def _hallucination_risk(response: str) -> float:
    """Heuristic hallucination risk in [0, 1].

    High risk: very certain language with no hedging, very long responses.
    Low risk: hedged language, appropriate brevity.
    """
    lower = response.lower()
    certainty = sum(1 for p in _CERTAINTY_PATTERNS if p in lower)
    hedging = sum(1 for p in _HEDGE_PATTERNS if p in lower)
    length_factor = min(1.0, len(response.split()) / 500)

    if hedging > 0:
        certainty = max(0, certainty - hedging)

    risk = min(1.0, (certainty * 0.2) + (length_factor * 0.3))
    return round(risk, 3)


class Evaluator:
    """Evaluation pipeline for LLM responses.

    Args:
        pass_fn:     Optional custom pass/fail function: (prompt, response) → bool.
                     Defaults to len(response) > 0.
        cost_per_1k: Token cost in abstract units per 1000 tokens (for reporting).
    """

    def __init__(
        self,
        pass_fn: Callable[[str, str], bool] | None = None,
        cost_per_1k: float = 1.0,
    ) -> None:
        self._pass_fn = pass_fn or (lambda p, r: len(r.strip()) > 0)
        self._cost_per_1k = cost_per_1k
        self._records: list[EvalRecord] = []

    def record(
        self,
        prompt: str,
        response: str,
        latency_ms: float,
        tokens_used: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> EvalRecord:
        """Record one evaluation. Returns the EvalRecord."""
        if tokens_used == 0:
            tokens_used = max(1, (len(prompt) + len(response)) // 4)

        rec = EvalRecord(
            prompt=prompt,
            response=response,
            latency_ms=round(latency_ms, 2),
            tokens_used=tokens_used,
            passed=self._pass_fn(prompt, response),
            hallucination_risk=_hallucination_risk(response),
            metadata=metadata or {},
        )
        self._records.append(rec)
        return rec

    def measure(self, fn: Callable[[], str], prompt: str = "") -> EvalRecord:
        """Time and evaluate *fn()* in one call."""
        t0 = time.perf_counter()
        response = fn()
        latency_ms = (time.perf_counter() - t0) * 1000
        return self.record(prompt, response, latency_ms)

    def aggregate(self) -> EvalMetrics:
        """Compute aggregate metrics over all recorded evaluations."""
        if not self._records:
            return EvalMetrics()

        n = len(self._records)
        return EvalMetrics(
            count=n,
            avg_latency_ms=round(sum(r.latency_ms for r in self._records) / n, 2),
            avg_tokens=round(sum(r.tokens_used for r in self._records) / n, 1),
            avg_hallucination_risk=round(
                sum(r.hallucination_risk for r in self._records) / n, 3
            ),
            pass_rate=round(sum(1 for r in self._records if r.passed) / n, 3),
            total_cost_tokens=sum(r.tokens_used for r in self._records),
        )

    def regression_check(self, baseline: EvalMetrics, tolerance: float = 0.1) -> dict[str, bool]:
        """Compare current metrics against a baseline.

        Returns {metric: True if within tolerance}.
        """
        current = self.aggregate()
        return {
            "latency_ok": current.avg_latency_ms <= baseline.avg_latency_ms * (1 + tolerance),
            "hallucination_ok": current.avg_hallucination_risk <= baseline.avg_hallucination_risk + tolerance,
            "pass_rate_ok": current.pass_rate >= baseline.pass_rate - tolerance,
        }

    def records(self) -> list[EvalRecord]:
        return list(self._records)

    def reset(self) -> None:
        self._records = []

    def cost_estimate(self) -> float:
        total_tokens = sum(r.tokens_used for r in self._records)
        return (total_tokens / 1000) * self._cost_per_1k

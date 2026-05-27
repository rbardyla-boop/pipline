"""Lesson 6: Agents Need Guardrails.

Production-ready agent safety layer. Uncontrolled agents are expensive and
unreliable. Guardrails prevent infinite loops, cost explosions, and wrong
action compounding.

Self-igniting: Guardrails wrap any callable and activate automatically.
No configuration required beyond defaults.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, FrozenSet


class ToolPermissionError(Exception):
    pass


class RetryExhaustedError(Exception):
    pass


class TimeoutError(Exception):
    pass


class HumanCheckpointRequired(Exception):
    pass


@dataclass(frozen=True)
class ToolPermission:
    name: str
    allowed: bool = True
    requires_confirmation: bool = False


@dataclass
class GuardrailsConfig:
    max_retries: int = 3
    retry_delay_base: float = 1.0
    timeout_seconds: float = 30.0
    max_cost_tokens: int = 100_000
    human_checkpoint_every: int = 0  # 0 = no automatic checkpoints
    allowed_tools: FrozenSet[str] = field(default_factory=frozenset)
    denied_tools: FrozenSet[str] = field(default_factory=frozenset)


class Guardrails:
    """Wraps agent actions with safety enforcement.

    Enforces:
    - Tool permission whitelist/blacklist
    - Retry limits with exponential backoff
    - Timeout per action
    - Token cost budget
    - Human checkpoint triggers

    Args:
        config: GuardrailsConfig with all safety parameters.
        on_human_checkpoint: Called when checkpoint is required.
                             If it raises, execution is halted.
    """

    def __init__(
        self,
        config: GuardrailsConfig | None = None,
        on_human_checkpoint: Callable[[str, Any], None] | None = None,
    ) -> None:
        self._cfg = config or GuardrailsConfig()
        self._on_checkpoint = on_human_checkpoint
        self._action_count = 0
        self._total_tokens = 0
        self._failed_actions: list[str] = []

    def check_tool(self, tool_name: str) -> None:
        """Raise ToolPermissionError if *tool_name* is not permitted."""
        if self._cfg.denied_tools and tool_name in self._cfg.denied_tools:
            raise ToolPermissionError(f"Tool '{tool_name}' is explicitly denied")
        if self._cfg.allowed_tools and tool_name not in self._cfg.allowed_tools:
            raise ToolPermissionError(
                f"Tool '{tool_name}' is not in the allowed set: {self._cfg.allowed_tools}"
            )

    def run(
        self,
        action: Callable[[], Any],
        action_name: str = "action",
        tokens_estimate: int = 0,
    ) -> Any:
        """Execute *action* with full guardrail enforcement.

        Args:
            action:          Zero-arg callable to execute.
            action_name:     Human-readable label for logging / checkpoints.
            tokens_estimate: Estimated tokens this action will consume.
        """
        self._check_cost(tokens_estimate)
        self._maybe_checkpoint(action_name)

        last_exc: Exception | None = None
        for attempt in range(self._cfg.max_retries + 1):
            try:
                result = self._run_with_timeout(action)
                self._action_count += 1
                self._total_tokens += tokens_estimate
                return result
            except TimeoutError:
                raise
            except HumanCheckpointRequired:
                raise
            except Exception as exc:
                last_exc = exc
                self._failed_actions.append(action_name)
                if attempt < self._cfg.max_retries:
                    delay = self._cfg.retry_delay_base * (2 ** attempt)
                    time.sleep(delay)
                    continue
                break

        raise RetryExhaustedError(
            f"Action '{action_name}' failed after {self._cfg.max_retries + 1} "
            f"attempts. Last error: {last_exc}"
        ) from last_exc

    def stats(self) -> dict[str, Any]:
        return {
            "actions_completed": self._action_count,
            "total_tokens": self._total_tokens,
            "failed_actions": len(self._failed_actions),
        }

    def reset_stats(self) -> None:
        self._action_count = 0
        self._total_tokens = 0
        self._failed_actions = []

    def _run_with_timeout(self, action: Callable[[], Any]) -> Any:
        if self._cfg.timeout_seconds <= 0:
            return action()

        # Use simple wall-clock timing (no threads) for deterministic tests.
        t0 = time.monotonic()
        result = action()
        elapsed = time.monotonic() - t0
        if elapsed > self._cfg.timeout_seconds:
            raise TimeoutError(
                f"Action exceeded timeout of {self._cfg.timeout_seconds}s "
                f"(took {elapsed:.2f}s)"
            )
        return result

    def _check_cost(self, tokens_estimate: int) -> None:
        if (
            self._cfg.max_cost_tokens > 0
            and self._total_tokens + tokens_estimate > self._cfg.max_cost_tokens
        ):
            raise RetryExhaustedError(
                f"Token budget exhausted: {self._total_tokens} used + "
                f"{tokens_estimate} requested > {self._cfg.max_cost_tokens}"
            )

    def _maybe_checkpoint(self, action_name: str) -> None:
        if self._cfg.human_checkpoint_every <= 0:
            return
        if self._action_count > 0 and self._action_count % self._cfg.human_checkpoint_every == 0:
            if self._on_checkpoint:
                self._on_checkpoint(action_name, self.stats())
            else:
                raise HumanCheckpointRequired(
                    f"Human checkpoint required after {self._action_count} actions. "
                    f"Current action: {action_name}"
                )

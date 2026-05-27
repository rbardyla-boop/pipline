"""Lesson 10: The Future Is Multi-Agent Systems.

Specialized agents working together. Each handles a specific responsibility.
The registry dispatches by capability. Results are isolated so failures
don't cascade.

Self-igniting: register agents with capabilities, queries self-route.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class AgentSpec:
    """Describes an agent and its capabilities."""
    agent_id: str
    capabilities: frozenset[str]
    description: str = ""
    priority: int = 0  # higher = preferred when multiple match


@dataclass
class AgentResult:
    agent_id: str
    query: str
    result: Any
    success: bool
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentRegistry:
    """Multi-agent orchestration registry.

    Agents are registered with capability tags. Queries are dispatched to
    the best-matching agent. Multiple agents can run in sequence or
    concurrently (via run_all).

    Args:
        fallback_fn: Called when no agent matches. Returns a fallback result.
    """

    def __init__(
        self,
        fallback_fn: Callable[[str], Any] | None = None,
    ) -> None:
        self._agents: dict[str, tuple[AgentSpec, Callable[[str], Any]]] = {}
        self._fallback = fallback_fn

    def register(
        self,
        spec: AgentSpec,
        handler: Callable[[str], Any],
    ) -> None:
        """Register an agent handler for the given spec."""
        self._agents[spec.agent_id] = (spec, handler)

    def unregister(self, agent_id: str) -> bool:
        return bool(self._agents.pop(agent_id, None))

    def dispatch(self, query: str, capability: str | None = None) -> AgentResult:
        """Route *query* to the best-matching agent.

        If *capability* is given, only agents with that capability are
        considered. Otherwise, all agents are eligible and the highest
        priority one is chosen.
        """
        candidates = self._find_candidates(capability)
        if not candidates:
            return self._fallback_result(query, capability)

        # Pick highest-priority agent
        spec, handler = max(candidates, key=lambda x: x[0].priority)
        return self._invoke(spec, handler, query)

    def run_all(
        self,
        query: str,
        capability: str | None = None,
        stop_on_first_success: bool = False,
    ) -> list[AgentResult]:
        """Run all matching agents. Returns list of results in priority order."""
        candidates = sorted(
            self._find_candidates(capability),
            key=lambda x: x[0].priority,
            reverse=True,
        )
        results = []
        for spec, handler in candidates:
            result = self._invoke(spec, handler, query)
            results.append(result)
            if stop_on_first_success and result.success:
                break
        return results

    def capabilities(self) -> set[str]:
        """Return all registered capability tags."""
        caps: set[str] = set()
        for spec, _ in self._agents.values():
            caps.update(spec.capabilities)
        return caps

    def agent_ids(self) -> list[str]:
        return list(self._agents.keys())

    def _find_candidates(
        self, capability: str | None
    ) -> list[tuple[AgentSpec, Callable[[str], Any]]]:
        if capability is None:
            return list(self._agents.values())
        return [
            (spec, fn)
            for spec, fn in self._agents.values()
            if capability in spec.capabilities
        ]

    def _invoke(
        self,
        spec: AgentSpec,
        handler: Callable[[str], Any],
        query: str,
    ) -> AgentResult:
        try:
            result = handler(query)
            return AgentResult(
                agent_id=spec.agent_id,
                query=query,
                result=result,
                success=True,
            )
        except Exception as exc:
            return AgentResult(
                agent_id=spec.agent_id,
                query=query,
                result=None,
                success=False,
                error=str(exc),
            )

    def _fallback_result(self, query: str, capability: str | None) -> AgentResult:
        if self._fallback:
            try:
                result = self._fallback(query)
                return AgentResult("fallback", query, result, True)
            except Exception as exc:
                return AgentResult("fallback", query, None, False, str(exc))
        return AgentResult(
            agent_id="none",
            query=query,
            result=None,
            success=False,
            error=f"No agent found for capability='{capability}'",
        )

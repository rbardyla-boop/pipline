"""RuntimeEnvironment — the bridge between cognition and execution world.

The runtime is the governance choke point: all external calls (LLMs,
search APIs, file I/O) must pass through secure_call(), which routes
through the security layer and audit log. This makes the runtime the
single seam where LlamaFirewall, gateway clients, and future sandbox
runtimes are wired in.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable


class RuntimeEnvironment(ABC):
    """Governance-enforced bridge to external systems."""

    @abstractmethod
    def ingest_context(self, domain: str) -> str:
        """Fetch and return the zeitgeist / cultural context string for *domain*.

        Implementations handle caching, fallback signals, and embedding.
        Returns a plain text block ready to inject into the cognition prompt.
        """

    @abstractmethod
    def secure_call(self, fn: Callable, *args: Any, **kwargs: Any) -> Any:
        """Execute *fn* with *args* / *kwargs* through the security layer.

        All LLM calls and external API calls must flow through here.
        Implementations must:
          1. Pre-scan inputs for injection patterns (LlamaFirewall or equivalent).
          2. Execute the call.
          3. Post-scan outputs for credential leakage / injection payloads.
          4. Raise or return a sentinel on scan failure rather than propagating
             a potentially poisoned result.
        """

    @abstractmethod
    def persist(self, key: str, payload: dict) -> None:
        """Write *payload* to a named persistent store (logs, archive, audit).

        *key* is a logical name (e.g. "run_log", "audit_record", "terminal_archive").
        Implementations resolve the physical path from config.
        """

    @abstractmethod
    def run_id(self) -> str:
        """Return the unique identifier for the current simulation run.

        Must be stable for the lifetime of a single run and unique across runs.
        """

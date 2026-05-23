"""LocalRuntime — wraps ZeitgeistInjector + security layer as a RuntimeEnvironment.

The runtime is the governance choke point: all external calls route through
secure_call(), which delegates to LlamaFirewallClient's pre/post injection
scanning. File I/O for run logs, audit records, and the terminal archive
routes through persist().
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from uaf.interfaces.runtime import RuntimeEnvironment


class LocalRuntime(RuntimeEnvironment):
    """RuntimeEnvironment for local (non-containerised) execution.

    Args:
        zeitgeist:     A ZeitgeistInjector instance for cultural context.
        log_dir:       Base directory for run logs (default: logs/).
        run_id_prefix: Optional prefix for generated run IDs.
    """

    _LOG_TARGETS = {
        "run_log": "logs/runs",
        "audit_record": "logs/audit",
        "terminal_archive": "logs",  # terminal_archive.json lives directly here
    }

    def __init__(
        self,
        zeitgeist,           # ZeitgeistInjector — loosely typed to avoid heavy import at module level
        log_dir: str = "logs",
        run_id_prefix: str = "uaf",
    ) -> None:
        self._zeitgeist = zeitgeist
        self._log_dir = log_dir
        self._run_id_prefix = run_id_prefix
        self._run_id: str = self._generate_run_id()

    def _generate_run_id(self) -> str:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        uid = uuid.uuid4().hex[:6]
        return f"{self._run_id_prefix}_{ts}_{uid}"

    # ------------------------------------------------------------------ #
    # RuntimeEnvironment                                                  #
    # ------------------------------------------------------------------ #

    def ingest_context(self, domain: str) -> str:
        return self._zeitgeist.get_formatted_context(domain)

    def secure_call(self, fn: Callable, *args: Any, **kwargs: Any) -> Any:
        """Execute *fn* directly.

        In the current LocalRuntime, the security scanning is embedded
        inside LlamaFirewallClient (which all Claude callers already use).
        This method exists as the explicit governance seam — future
        implementations can wrap it with additional policy enforcement.
        """
        return fn(*args, **kwargs)

    def persist(self, key: str, payload: dict) -> None:
        if key == "terminal_archive":
            self._persist_terminal_archive(payload)
        else:
            base = self._LOG_TARGETS.get(key, self._log_dir)
            Path(base).mkdir(parents=True, exist_ok=True)
            filepath = Path(base) / f"{key}_{self._run_id}.json"
            with open(filepath, "w") as f:
                json.dump(payload, f, indent=2)

    def run_id(self) -> str:
        return self._run_id

    # ------------------------------------------------------------------ #
    # Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    def _persist_terminal_archive(self, payload: dict) -> None:
        """Append a single terminal-archive entry to the shared JSON file."""
        import hashlib

        terminal_path = os.getenv("TERMINAL_ARCHIVE_PATH", "logs/terminal_archive.json")
        Path("logs").mkdir(exist_ok=True)

        entries: list = []
        try:
            with open(terminal_path) as f:
                entries = json.load(f)
        except FileNotFoundError:
            pass

        concept = payload.get("concept", "")
        concept_hash = hashlib.sha256(concept.encode()).hexdigest()[:16]
        if any(e.get("concept_hash") == concept_hash for e in entries):
            return  # already retired

        entries.append({
            "concept_hash": concept_hash,
            "concept_preview": concept[:120] + "...",
            "phoenix_score": payload.get("phoenix_score", 0.0),
            "combined": payload.get("combined", 0.0),
            "run_id": self._run_id,
            "retired_at": datetime.now().strftime("%Y%m%d_%H%M%S"),
        })
        with open(terminal_path, "w") as f:
            json.dump(entries, f, indent=2)

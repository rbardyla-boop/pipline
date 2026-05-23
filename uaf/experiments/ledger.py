"""ExperimentLedger — persistent store of experiment traces.

The ledger is a JSON-lines file (one record per run) that enables
cross-run and cross-architecture comparison. It is the research database
for the UAF system.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from uaf.experiments.runner import ExperimentTrace


class ExperimentLedger:
    """Append-only JSON-lines ledger for experiment traces.

    Args:
        path: Path to the ledger file.
              Defaults to EXPERIMENT_LEDGER_PATH env var or
              "logs/experiment_ledger.jsonl".
    """

    def __init__(self, path: str | None = None) -> None:
        self._path = path or os.getenv(
            "EXPERIMENT_LEDGER_PATH", "logs/experiment_ledger.jsonl"
        )
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)

    def record(self, trace: ExperimentTrace) -> None:
        """Append *trace* to the ledger."""
        with open(self._path, "a") as f:
            f.write(json.dumps(trace.to_dict()) + "\n")

    def load_all(self) -> list[dict]:
        """Return all recorded traces as a list of dicts."""
        if not Path(self._path).exists():
            return []
        records = []
        with open(self._path) as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records

    def load_by_architecture(self, architecture_id: str) -> list[dict]:
        """Return all traces for a given architecture."""
        return [r for r in self.load_all() if r.get("architecture_id") == architecture_id]

    def load_by_experiment(self, experiment_id: str) -> list[dict]:
        """Return all traces for a given experiment ID."""
        return [r for r in self.load_all() if r.get("experiment_id") == experiment_id]

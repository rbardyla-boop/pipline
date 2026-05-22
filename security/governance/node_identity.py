"""
Per-node identity contracts for the LangGraph pipeline.

Each pipeline node declares:
- Its identity (immutable string ID)
- Its permitted outbound calls (allowlist)
- Whether it may call LLM APIs

Violations are logged as constitutional failures. In strict mode (env
STRICT_NODE_GOVERNANCE=true), violations raise RuntimeError.
"""
from __future__ import annotations

import os
import logging
from dataclasses import dataclass, field
from typing import FrozenSet

log = logging.getLogger(__name__)

STRICT = os.getenv("STRICT_NODE_GOVERNANCE", "false").lower() == "true"


@dataclass(frozen=True)
class NodeIdentity:
    node_id: str
    may_call_llm: bool
    may_call_network: bool
    permitted_imports: FrozenSet[str]

    def assert_can_call_llm(self) -> None:
        if not self.may_call_llm:
            msg = f"[GOVERNANCE] Node '{self.node_id}' is not permitted to call LLM APIs"
            log.error(msg)
            if STRICT:
                raise RuntimeError(msg)

    def assert_can_call_network(self) -> None:
        if not self.may_call_network:
            msg = f"[GOVERNANCE] Node '{self.node_id}' is not permitted to call network APIs"
            log.error(msg)
            if STRICT:
                raise RuntimeError(msg)


# ── Node registry ─────────────────────────────────────────────────────────────
# Maps LangGraph node name → identity contract.
# signals.py is not a node but is listed as a reference for CI enforcement.

NODES: dict[str, NodeIdentity] = {
    "signals": NodeIdentity(
        node_id="signals",
        may_call_llm=False,
        may_call_network=False,
        permitted_imports=frozenset(["re", "math", "dataclasses", "typing"]),
    ),
    "ingest": NodeIdentity(
        node_id="ingest",
        may_call_llm=False,
        may_call_network=True,  # Tavily via gateway
        permitted_imports=frozenset(["zeitgeist", "security.gateway"]),
    ),
    "entropy": NodeIdentity(
        node_id="entropy",
        may_call_llm=False,
        may_call_network=False,
        permitted_imports=frozenset(["typing"]),
    ),
    "mutate": NodeIdentity(
        node_id="mutate",
        may_call_llm=True,  # Claude via firewall
        may_call_network=False,
        permitted_imports=frozenset(["engine", "security.firewall"]),
    ),
    "sandbox": NodeIdentity(
        node_id="sandbox",
        may_call_llm=False,
        may_call_network=False,
        permitted_imports=frozenset(["sandbox"]),
    ),
    "refine": NodeIdentity(
        node_id="refine",
        may_call_llm=True,  # Claude via firewall
        may_call_network=False,
        permitted_imports=frozenset(["concept_rater", "engine", "security.firewall"]),
    ),
    "save": NodeIdentity(
        node_id="save",
        may_call_llm=False,
        may_call_network=False,
        permitted_imports=frozenset(["json", "pathlib", "datetime", "engine"]),
    ),
}


def get_node(node_id: str) -> NodeIdentity:
    if node_id not in NODES:
        raise KeyError(f"Unknown node: '{node_id}'")
    return NODES[node_id]

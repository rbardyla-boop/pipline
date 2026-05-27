"""Lesson 4: Prompt Engineering Is System Engineering.

Multi-layer prompt orchestration. Good prompts are not magic spells —
they are structured systems with role separation, dynamic injection,
and budget-aware assembly.

Self-igniting: start with empty layers, add content, assemble on demand.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any


class PromptLayer(IntEnum):
    """Assembly order (low → rendered first in the final prompt)."""
    SYSTEM = 10          # role, persona, global constraints
    SAFETY = 20          # safety constraints, output format rules
    TOOL_INSTRUCTIONS = 30  # how to use available tools
    CONTEXT = 40         # retrieved knowledge, memory
    HISTORY = 50         # conversation history
    TASK = 60            # current task description
    USER = 70            # the actual user message


@dataclass
class _LayerSlot:
    layer: PromptLayer
    content: str
    tokens: int
    label: str = ""


def _count_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class PromptSystem:
    """Structured multi-prompt builder.

    Manages named slots at each layer. Assembles in layer order with
    optional token budget enforcement.

    Args:
        token_budget: If > 0, enforce a cap and drop CONTEXT/HISTORY first.
        separator:    String inserted between layers in the assembled prompt.
    """

    def __init__(self, token_budget: int = 0, separator: str = "\n\n") -> None:
        self._token_budget = token_budget
        self._separator = separator
        self._slots: dict[str, _LayerSlot] = {}

    def set(
        self,
        label: str,
        content: str,
        layer: PromptLayer = PromptLayer.CONTEXT,
    ) -> "PromptSystem":
        """Add or replace a named slot. Returns self for chaining."""
        tokens = _count_tokens(content)
        self._slots[label] = _LayerSlot(layer, content, tokens, label)
        return self

    def remove(self, label: str) -> bool:
        return bool(self._slots.pop(label, None))

    def inject(self, variables: dict[str, Any]) -> "PromptSystem":
        """Replace {{key}} placeholders in all slots with values from *variables*."""
        for slot in self._slots.values():
            for k, v in variables.items():
                slot.content = slot.content.replace("{{" + k + "}}", str(v))
                slot.tokens = _count_tokens(slot.content)
        return self

    def assemble(self, include_layers: set[PromptLayer] | None = None) -> str:
        """Build the final prompt string.

        If *include_layers* is given, only those layers are included.
        If token_budget is set, lower-priority layers are dropped to fit.
        """
        slots = sorted(self._slots.values(), key=lambda s: s.layer)
        if include_layers is not None:
            slots = [s for s in slots if s.layer in include_layers]

        if self._token_budget > 0:
            slots = self._enforce_budget(slots)

        return self._separator.join(s.content for s in slots if s.content.strip())

    def token_estimate(self) -> int:
        return sum(s.tokens for s in self._slots.values())

    def layer_summary(self) -> dict[str, int]:
        """Return {layer_name: total_tokens} for each occupied layer."""
        summary: dict[str, int] = {}
        for slot in self._slots.values():
            name = slot.layer.name
            summary[name] = summary.get(name, 0) + slot.tokens
        return summary

    def clone(self) -> "PromptSystem":
        """Return a deep copy."""
        ps = PromptSystem(self._token_budget, self._separator)
        for label, slot in self._slots.items():
            ps._slots[label] = _LayerSlot(
                slot.layer, slot.content, slot.tokens, slot.label
            )
        return ps

    def _enforce_budget(self, slots: list[_LayerSlot]) -> list[_LayerSlot]:
        """Drop slots starting from lowest priority until budget fits."""
        total = sum(s.tokens for s in slots)
        if total <= self._token_budget:
            return slots

        droppable_layers = [PromptLayer.HISTORY, PromptLayer.CONTEXT]
        result = list(slots)
        for drop_layer in droppable_layers:
            if total <= self._token_budget:
                break
            droppable = [s for s in result if s.layer == drop_layer]
            for s in sorted(droppable, key=lambda x: -x.tokens):
                if total <= self._token_budget:
                    break
                result.remove(s)
                total -= s.tokens

        return result

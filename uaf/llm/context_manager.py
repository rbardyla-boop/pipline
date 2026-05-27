"""Lesson 2: Context Is Your Real Database.

Context window manager that treats the context as working memory — deciding
what deserves attention, compressing intelligently, and never wasting tokens.

Self-igniting: starts from empty and builds as entries are added. No seed needed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Callable


class ContextPriority(IntEnum):
    CRITICAL = 5   # system instructions, safety constraints
    HIGH = 4       # current task, user query
    MEDIUM = 3     # recent history, retrieved context
    LOW = 2        # background knowledge
    EPHEMERAL = 1  # intermediate reasoning, one-shot fillers


@dataclass
class ContextEntry:
    content: str
    priority: ContextPriority
    tokens: int
    label: str = ""
    compressible: bool = True

    def __post_init__(self) -> None:
        if self.tokens <= 0:
            raise ValueError("tokens must be positive")


@dataclass
class ContextManager:
    """Manages a context window budget.

    Keeps high-priority entries, compresses or evicts low-priority ones
    when the budget is exceeded. Thread-safe if callers serialize access.

    Args:
        max_tokens:   Hard budget for the total context (e.g. 8192).
        token_counter: Callable that estimates token count for a string.
                       Defaults to len(text) // 4 (rough GPT approximation).
    """

    max_tokens: int = 8192
    token_counter: Callable[[str], int] = field(
        default_factory=lambda: (lambda text: max(1, len(text) // 4))
    )
    _entries: list[ContextEntry] = field(default_factory=list, init=False)
    _used_tokens: int = field(default=0, init=False)

    def add(
        self,
        content: str,
        priority: ContextPriority = ContextPriority.MEDIUM,
        label: str = "",
        compressible: bool = True,
    ) -> bool:
        """Add an entry. Returns True if added, False if budget is exhausted."""
        tokens = self.token_counter(content)
        entry = ContextEntry(content, priority, tokens, label, compressible)

        if self._used_tokens + tokens > self.max_tokens:
            if not self._evict(tokens):
                return False

        self._entries.append(entry)
        self._used_tokens += tokens
        return True

    def build(self) -> str:
        """Assemble entries sorted by priority (highest first)."""
        ordered = sorted(self._entries, key=lambda e: e.priority, reverse=True)
        return "\n\n".join(e.content for e in ordered)

    def used_tokens(self) -> int:
        return self._used_tokens

    def remaining_tokens(self) -> int:
        return self.max_tokens - self._used_tokens

    def utilization(self) -> float:
        return self._used_tokens / self.max_tokens

    def clear_tier(self, priority: ContextPriority) -> int:
        """Remove all entries at *priority*. Returns tokens freed."""
        freed = 0
        kept = []
        for e in self._entries:
            if e.priority == priority:
                freed += e.tokens
            else:
                kept.append(e)
        self._entries = kept
        self._used_tokens -= freed
        return freed

    def reset(self) -> None:
        self._entries = []
        self._used_tokens = 0

    def _evict(self, needed: int) -> bool:
        """Evict compressible low-priority entries until *needed* tokens free."""
        candidates = sorted(
            [e for e in self._entries if e.compressible],
            key=lambda e: (e.priority, -e.tokens),
        )
        freed = 0
        evicted = set()
        for c in candidates:
            if freed >= needed:
                break
            freed += c.tokens
            evicted.add(id(c))

        if freed < needed:
            return False

        self._entries = [e for e in self._entries if id(e) not in evicted]
        self._used_tokens -= freed
        return True

    def __len__(self) -> int:
        return len(self._entries)

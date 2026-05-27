"""LLMCognitionEngine — CognitionEngine implementation using all 10 LLM architecture lessons.

This engine self-ignites: the moment it is instantiated, all subsystems
bootstrap from empty state and sustain through internal feedback loops.
No external ignition required.

Lessons wired together:
  1. Workflow-first        → UAF SimulationKernel drives the loop
  2. Context as DB         → ContextManager manages what goes in the prompt
  3. Retrieval before FT   → RetrievalPipeline retrieves relevant context
  4. Prompt is system eng  → PromptSystem assembles structured prompts
  5. Latency matters       → ModelRouter routes to right model tier
  6. Agents need guardrails→ Guardrails wraps all LLM calls
  7. Memory is hard        → MemoryStack holds session + long-term memory
  8. Eval pipelines        → Evaluator records every call
  9. Cost optimization     → Router caching + token budget
  10. Multi-agent future   → AgentRegistry dispatches specialized tasks
"""

from __future__ import annotations

import math
from typing import Sequence

from uaf.interfaces.cognition import CognitionEngine
from uaf.llm.context_manager import ContextManager, ContextPriority
from uaf.llm.retrieval import RetrievalPipeline, Document
from uaf.llm.prompt_system import PromptSystem, PromptLayer
from uaf.llm.guardrails import Guardrails, GuardrailsConfig
from uaf.llm.memory_stack import MemoryStack
from uaf.llm.evaluator import Evaluator
from uaf.llm.router import ModelRouter, Complexity
from uaf.llm.multi_agent import AgentRegistry, AgentSpec


def _simple_embed(text: str) -> list[float]:
    """Deterministic BoW embedding — no external deps, no GPU."""
    tokens = text.lower().split()
    counts: dict[str, int] = {}
    for t in tokens:
        counts[t] = counts.get(t, 0) + 1
    total = max(1, len(tokens))
    keys = sorted(counts.keys())
    vec = [counts[k] / total for k in keys]
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def _cosine(a: list[float], b: list[float]) -> float:
    shared = min(len(a), len(b))
    dot = sum(a[i] * b[i] for i in range(shared))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)


class LLMCognitionEngine(CognitionEngine):
    """Self-igniting LLM architecture engine.

    Instantiating this class fires up all 10 subsystems. No external
    dependencies required — works without a real LLM API by using a
    deterministic mutation strategy based on semantic similarity.

    Args:
        propose_fn: Callable(parent, context, prompt) → candidate string.
                    If None, falls back to a local heuristic mutator.
        token_budget: Max tokens for the context window.
        max_retries:  Guardrail retry limit.
    """

    def __init__(
        self,
        propose_fn=None,
        token_budget: int = 4096,
        max_retries: int = 3,
    ) -> None:
        # Lesson 2: Context
        self._ctx = ContextManager(max_tokens=token_budget)
        # Lesson 3: Retrieval
        self._retrieval = RetrievalPipeline(embed_fn=_simple_embed)
        # Lesson 4: Prompt system
        self._prompts = PromptSystem(token_budget=token_budget)
        # Lesson 5 + 9: Router + caching
        self._router = ModelRouter(cache_capacity=128)
        # Lesson 6: Guardrails
        self._guardrails = Guardrails(GuardrailsConfig(max_retries=max_retries, retry_delay_base=0.0))
        # Lesson 7: Memory
        self._memory = MemoryStack(short_window=20, mid_capacity=100, summarize_at=10)
        # Lesson 8: Evaluator
        self._evaluator = Evaluator()
        # Lesson 10: Multi-agent registry (for specialized sub-tasks)
        self._agents = AgentRegistry(fallback_fn=lambda q: q)
        self._register_default_agents()

        self._propose_fn = propose_fn or self._local_mutate
        self._last_trace: list[str] = []

    # ------------------------------------------------------------------ #
    # CognitionEngine interface                                            #
    # ------------------------------------------------------------------ #

    def propose(self, parent: str, context: str) -> str:
        """Generate a mutated candidate using the full LLM pipeline."""
        # Lesson 3: Retrieve related context
        related = self._retrieval.query(parent, top_k=3)
        retrieved_text = "\n".join(r.document.text for r in related)

        # Lesson 2: Build context window
        self._ctx.reset()
        self._ctx.add(context, ContextPriority.HIGH, label="zeitgeist")
        if retrieved_text:
            self._ctx.add(retrieved_text, ContextPriority.MEDIUM, label="retrieved")

        # Lesson 7: Recall relevant memories
        memories = self._memory.recall(parent, top_k=2)
        for m in memories:
            self._ctx.add(m, ContextPriority.LOW, label="memory", compressible=True)

        # Lesson 4: Assemble structured prompt
        self._prompts.set("system", "You are a creative extrapolation engine.", PromptLayer.SYSTEM)
        self._prompts.set("context", self._ctx.build(), PromptLayer.CONTEXT)
        self._prompts.set("task", f"Mutate this concept beyond its genre:\n{parent}", PromptLayer.TASK)
        assembled_prompt = self._prompts.assemble()

        # Lesson 5: Route to appropriate model
        decision = self._router.route(assembled_prompt)

        # Lesson 6: Execute with guardrails
        def _call():
            return self._propose_fn(parent, context, assembled_prompt)

        candidate = self._guardrails.run(_call, "propose", tokens_estimate=decision.token_estimate)

        # Lesson 8: Record for evaluation
        self._evaluator.record(assembled_prompt, candidate, latency_ms=1.0)

        # Lesson 7: Store in memory
        self._memory.push("engine", candidate[:200])
        self._retrieval.add(Document(text=candidate, doc_id=f"gen_{id(candidate)}"))

        self._last_trace = [
            f"route={decision.model} complexity={decision.complexity.value}",
            f"ctx_tokens={self._ctx.used_tokens()} retrieved={len(related)}",
            f"guardrail_stats={self._guardrails.stats()}",
        ]
        return candidate

    def embed(self, text: str) -> Sequence[float]:
        return _simple_embed(text)

    def coherence(self, candidate: str) -> float:
        """Estimate coherence as inverse hallucination risk."""
        from uaf.llm.evaluator import _hallucination_risk
        risk = _hallucination_risk(candidate)
        # Longer non-trivial candidates are considered more coherent
        length_bonus = min(0.3, len(candidate.split()) / 100)
        return max(0.1, min(1.0, (1.0 - risk) * 0.7 + length_bonus))

    @property
    def architecture_id(self) -> str:
        return "llm_arch_v1"

    def reasoning_trace(self) -> list[str]:
        return list(self._last_trace)

    # ------------------------------------------------------------------ #
    # Seed the retrieval index with domain documents                       #
    # ------------------------------------------------------------------ #

    def seed_knowledge(self, documents: list[str]) -> None:
        """Pre-populate the retrieval index with domain knowledge."""
        for i, doc in enumerate(documents):
            self._retrieval.add(Document(text=doc, doc_id=f"seed_{i}"))

    # ------------------------------------------------------------------ #
    # Internal                                                             #
    # ------------------------------------------------------------------ #

    def _local_mutate(self, parent: str, context: str, prompt: str) -> str:
        """Deterministic local mutation — no API calls needed."""
        words = parent.split()
        ctx_words = context.split()

        # Inject context words into parent to create variation
        if ctx_words and len(words) > 2:
            pivot = len(words) // 2
            inject = ctx_words[: min(3, len(ctx_words))]
            mutated = words[:pivot] + inject + words[pivot:]
        else:
            mutated = words + [f"[{w}]" for w in words[:2]]

        return " ".join(mutated)

    def _register_default_agents(self) -> None:
        """Register specialized sub-agents (Lesson 10)."""
        self._agents.register(
            AgentSpec("context_agent", frozenset(["context", "retrieve"]), priority=1),
            lambda q: self._retrieval.query(q, top_k=2),
        )
        self._agents.register(
            AgentSpec("memory_agent", frozenset(["recall", "memory"]), priority=1),
            lambda q: self._memory.recall(q, top_k=3),
        )
        self._agents.register(
            AgentSpec("eval_agent", frozenset(["evaluate", "score"]), priority=1),
            lambda q: self._evaluator.aggregate(),
        )

"""LLM Architecture layer — 10 lessons implemented as self-igniting components.

Each component bootstraps itself from a minimal seed and sustains through
internal feedback, requiring no external ignition once started.
"""

from uaf.llm.context_manager import ContextManager, ContextEntry, ContextPriority
from uaf.llm.retrieval import RetrievalPipeline, Document, RetrievalResult
from uaf.llm.prompt_system import PromptSystem, PromptLayer
from uaf.llm.guardrails import Guardrails, GuardrailsConfig, ToolPermission
from uaf.llm.memory_stack import MemoryStack, MemoryTier
from uaf.llm.evaluator import Evaluator, EvalMetrics, EvalRecord
from uaf.llm.router import ModelRouter, Complexity, RouteDecision
from uaf.llm.multi_agent import AgentRegistry, AgentSpec, AgentResult
from uaf.llm.rms_norm import RMSNorm
from uaf.llm.metrics import bleu, rouge_n, rouge_l, exact_match, token_f1, BLEUScore, ROUGEScore
from uaf.llm.transformer import TransformerBlock, ScaledDotProductAttention, FeedForwardNetwork

__all__ = [
    "ContextManager", "ContextEntry", "ContextPriority",
    "RetrievalPipeline", "Document", "RetrievalResult",
    "PromptSystem", "PromptLayer",
    "Guardrails", "GuardrailsConfig", "ToolPermission",
    "MemoryStack", "MemoryTier",
    "Evaluator", "EvalMetrics", "EvalRecord",
    "ModelRouter", "Complexity", "RouteDecision",
    "AgentRegistry", "AgentSpec", "AgentResult",
    "RMSNorm",
    "bleu", "rouge_n", "rouge_l", "exact_match", "token_f1", "BLEUScore", "ROUGEScore",
    "TransformerBlock", "ScaledDotProductAttention", "FeedForwardNetwork",
]

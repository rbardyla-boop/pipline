"""
LlamaFirewall integration layer.

Wraps every anthropic.Anthropic().messages.create() call with:
- Pre-call: prompt injection scan on all message content
- Post-call: response scan for embedded injection / credential leakage

If the `llamafirewall` PyPI package is installed, delegates to it.
Otherwise falls back to a deterministic rule-based detector.

The outer interface is identical in both cases: `LlamaFirewallClient`
exposes the same API as `anthropic.Anthropic`, so call-sites need only
replace `Anthropic()` with `get_secure_client()`.
"""
from __future__ import annotations

import os
import re
import logging
from dataclasses import dataclass
from typing import Any

log = logging.getLogger(__name__)

# ── Injection patterns ────────────────────────────────────────────────────────
# These patterns detect common prompt injection and credential leakage attempts.
# Ordered from highest to lowest severity.

_INJECTION_PATTERNS: list[tuple[str, str]] = [
    # Credential extraction
    (r"(?i)(output|print|reveal|show|send|exfiltrate)\s+(your\s+)?(api[_\s]?key|secret|password|token|credential)", "credential_extraction"),
    (r"(?i)(ANTHROPIC|TAVILY|OPENAI)_API_KEY", "credential_pattern"),
    (r"(?i)sk-ant-[a-zA-Z0-9\-]+", "anthropic_key_leak"),
    # Role / system override
    (r"(?i)(ignore|disregard|forget)\s+(all\s+)?(previous|prior|above)\s+(instructions?|rules?|prompts?|context)", "system_override"),
    (r"(?i)(you\s+are\s+now|act\s+as|pretend\s+(to\s+be|you\s+are))\s+(an?\s+)?(different|new|another|evil|uncensored)", "role_injection"),
    (r"(?i)(system|assistant|human)\s*:\s*(ignore|override|bypass)", "role_prefix_injection"),
    # Special token injection (model-specific boundary tokens)
    (r"<\|im_(start|end|sep)\|>", "special_token_injection"),
    (r"\[INST\]|\[/INST\]|<<SYS>>|<</SYS>>", "llama_token_injection"),
    (r"###\s*(System|Instruction|Input|Response)\s*:", "alpaca_token_injection"),
    # Jailbreak patterns
    (r"(?i)dan\s*(mode|prompt|jailbreak|\b)", "dan_jailbreak"),
    (r"(?i)(enable|activate|unlock)\s+(developer|debug|god|admin|unrestricted)\s+mode", "mode_unlock"),
    (r"(?i)(ignore|remove|bypass|without)\s+(all\s+)?(restrictions?|filters?|safety|guardrails?|limitations?|rules?)", "safety_bypass"),
    (r"(?i)no\s+(restrictions?|filters?|safety|guardrails?)", "safety_bypass_no"),
    # Constitutional violations
    (r"(?i)(disable|bypass|skip|remove)\s+(safety|constitutional|ethical)\s+(checks?|filters?|constraints?)", "constitutional_bypass"),
]

_CREDENTIAL_LEAK_PATTERNS: list[tuple[str, str]] = [
    (r"sk-ant-[a-zA-Z0-9\-]{20,}", "anthropic_key"),
    (r"tvly-[a-zA-Z0-9\-]{20,}", "tavily_key"),
    (r"(?i)api[_\s]?key\s*[:=]\s*['\"]?[a-zA-Z0-9\-_]{20,}['\"]?", "generic_api_key"),
]

_COMPILED_INJECTION = [(re.compile(p), label) for p, label in _INJECTION_PATTERNS]
_COMPILED_LEAK = [(re.compile(p), label) for p, label in _CREDENTIAL_LEAK_PATTERNS]


@dataclass(frozen=True)
class ScanResult:
    blocked: bool
    reason: str | None
    pattern_id: str | None

    @classmethod
    def safe(cls) -> "ScanResult":
        return cls(blocked=False, reason=None, pattern_id=None)

    @classmethod
    def block(cls, reason: str, pattern_id: str) -> "ScanResult":
        return cls(blocked=True, reason=reason, pattern_id=pattern_id)


def _rule_scan(text: str, patterns: list[tuple[re.Pattern, str]]) -> ScanResult:
    for pattern, label in patterns:
        if pattern.search(text):
            return ScanResult.block(f"Pattern matched: {label}", label)
    return ScanResult.safe()


def scan_input(messages: list[dict]) -> ScanResult:
    """Scan message list before sending to LLM."""
    combined = " ".join(
        part if isinstance(part, str) else part.get("text", "")
        for msg in messages
        for part in ([msg.get("content")] if isinstance(msg.get("content"), str) else (msg.get("content") or []))
    )
    result = _rule_scan(combined, _COMPILED_INJECTION)
    if result.blocked:
        log.warning("[LLAMAFIREWALL] INPUT BLOCKED — %s", result.reason)
    return result


def scan_output(text: str) -> ScanResult:
    """Scan LLM response for injection bleed-through or credential leakage."""
    result = _rule_scan(text, _COMPILED_LEAK)
    if not result.blocked:
        result = _rule_scan(text, _COMPILED_INJECTION)
    if result.blocked:
        log.warning("[LLAMAFIREWALL] OUTPUT BLOCKED — %s", result.reason)
    return result


# ── LlamaFirewall backend (optional) ────────────────────────────────────────

def _try_llamafirewall_scan(text: str, scan_type: str) -> ScanResult | None:
    """Delegate to the real LlamaFirewall package if installed."""
    try:
        from llamafirewall import LlamaFirewall, ScannerType, UserMessage, AssistantMessage  # type: ignore[import]
        fw = LlamaFirewall()
        msg = UserMessage(content=text) if scan_type == "input" else AssistantMessage(content=text)
        decision = fw.scan(msg)
        if decision and decision.is_safe is False:
            return ScanResult.block(f"LlamaFirewall: {decision.reason}", "llamafirewall")
        return ScanResult.safe()
    except ImportError:
        return None


# ── Secure Anthropic client ──────────────────────────────────────────────────

class _SecureMessages:
    """Drop-in replacement for `anthropic.Anthropic().messages`."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner

    def create(self, **kwargs: Any) -> Any:
        messages = kwargs.get("messages", [])

        # Pre-call scan
        fw_result = _try_llamafirewall_scan(
            " ".join(
                (m.get("content") or "") if isinstance(m.get("content"), str)
                else " ".join(p.get("text", "") for p in (m.get("content") or []) if isinstance(p, dict))
                for m in messages
            ),
            "input"
        )
        if fw_result is None:
            fw_result = scan_input(messages)

        if fw_result.blocked:
            raise PermissionError(
                f"[LLAMAFIREWALL] Request blocked before LLM call. "
                f"Reason: {fw_result.reason}"
            )

        # Execute
        response = self._inner.create(**kwargs)

        # Post-call scan
        if response.content:
            response_text = " ".join(
                block.text for block in response.content if hasattr(block, "text")
            )
            out_result = _try_llamafirewall_scan(response_text, "output")
            if out_result is None:
                out_result = scan_output(response_text)
            if out_result.blocked:
                log.error("[LLAMAFIREWALL] Response blocked post-call. Reason: %s", out_result.reason)
                raise PermissionError(
                    f"[LLAMAFIREWALL] Response blocked post-LLM. "
                    f"Reason: {out_result.reason}"
                )

        return response


class LlamaFirewallClient:
    """
    Wraps `anthropic.Anthropic` with LlamaFirewall injection detection.

    Usage (drop-in):
        from security.firewall import LlamaFirewallClient
        client = LlamaFirewallClient()
        response = client.messages.create(...)
    """

    def __init__(self) -> None:
        import anthropic
        gateway_url = os.getenv("GATEWAY_URL")
        api_key = os.getenv("ANTHROPIC_API_KEY", "")

        if gateway_url:
            # Containerized mode: route through gateway (holds real credentials)
            self._client = anthropic.Anthropic(
                base_url=f"{gateway_url.rstrip('/')}/anthropic",
                api_key=api_key or "gateway-managed",
            )
        else:
            self._client = anthropic.Anthropic(api_key=api_key)

        self.messages = _SecureMessages(self._client.messages)

    # Expose RateLimitError / OverloadedError for call-site exception handling
    @property
    def _exceptions(self) -> Any:
        import anthropic
        return anthropic


def get_secure_client() -> LlamaFirewallClient:
    """Factory — returns a firewalled Anthropic client."""
    return LlamaFirewallClient()

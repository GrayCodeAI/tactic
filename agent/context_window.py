"""Approximate context-size estimation for prover proof sessions (tau port).

Provider-free, deterministic estimate over the dict-form message history that
the loop keeps.  The character-based heuristic (~4 chars/token) is good enough
for the auto-compaction budget and branch-summary token budgets; provider
usage is authoritative when present (see llm.LLMResponse.total_tokens).
"""

from __future__ import annotations

from dataclasses import dataclass

CHARS_PER_TOKEN = 4
MESSAGE_OVERHEAD_TOKENS = 4
TOOL_CALL_OVERHEAD_TOKENS = 16
SUMMARY_MESSAGE_CHAR_LIMIT = 500
COMPACTION_SUMMARY_PREFIX = "Previous conversation summary:\n"


@dataclass(frozen=True, slots=True)
class ContextUsageEstimate:
    """Best available context-size accounting for one provider request."""

    total_tokens: int
    system_tokens: int
    message_tokens: int
    tool_tokens: int
    message_count: int
    provider_tokens: int = 0

    @property
    def uses_provider_usage(self) -> bool:
        return self.provider_tokens > 0


def estimate_text_tokens(text: str) -> int:
    """Return a deterministic rough token estimate for text."""
    if not text:
        return 0
    return max(1, (len(text) + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN)


def _message_text(message: dict) -> str:
    content = message.get("content", "")
    if isinstance(content, (list, tuple)):
        parts = [str(c.get("text", "")) if isinstance(c, dict) else str(c) for c in content]
        return "\n".join(p for p in parts if p)
    return str(content) if content else ""


def estimate_message_tokens(message: dict) -> int:
    """Return a rough token estimate for one dict-form message."""
    tokens = MESSAGE_OVERHEAD_TOKENS + estimate_text_tokens(_message_text(message))
    if message.get("role") == "assistant":
        calls = message.get("tool_calls") or []
        tokens += sum(
            TOOL_CALL_OVERHEAD_TOKENS
            + estimate_text_tokens(str(c.get("name", "")) + str(c.get("arguments", "")))
            for c in calls
        )
    elif message.get("role") == "tool":
        tokens += estimate_text_tokens(str(message.get("name", "")))
    return tokens


def estimate_context_tokens(system: str, messages: list[dict]) -> int:
    """Return a rough estimate of the active provider context size."""
    return estimate_context_usage(system=system, messages=messages).total_tokens


def auto_compaction_threshold_for_context_window(context_window_tokens: int) -> int | None:
    """Return Pi-style automatic compaction threshold for a model context window."""
    from .llm import DEFAULT_COMPACTION_RESERVE_TOKENS

    if context_window_tokens <= 0:
        return None
    return max(1, context_window_tokens - DEFAULT_COMPACTION_RESERVE_TOKENS)


def estimate_context_usage(system: str, messages: list[dict]) -> ContextUsageEstimate:
    """Deterministic fallback context accounting (provider-free)."""
    system_tokens = estimate_text_tokens(system)
    message_tokens = sum(estimate_message_tokens(m) for m in messages)
    tool_tokens = sum(
        estimate_text_tokens(str(m.get("name", "")) + _message_text(m))
        for m in messages
        if m.get("role") == "tool"
    )
    total = system_tokens + message_tokens
    return ContextUsageEstimate(
        total_tokens=total,
        system_tokens=system_tokens,
        message_tokens=message_tokens,
        tool_tokens=tool_tokens,
        message_count=len(messages),
    )




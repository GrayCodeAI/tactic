"""Thinking-mode primitives for tactic proof sessions (tau thinking.py port).

Tau's levels are mapped onto tactic's single OpenAI-compatible endpoint:
- "off"            → vLLM/HF chat-template switch `enable_thinking: False`
                    (what TACTIC_DISABLE_THINKING=1 already does)
- minimal..xhigh   → OpenAI-compatible `reasoning_effort` value, same label.

`TACTIC_THINKING` (or the TUI /thinking command) sets the level;
TACTIC_DISABLE_THINKING=1 keeps its meaning as a hard "off" switch and wins
over TACTIC_THINKING when the two disagree.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Literal

__all__ = [
    "DEFAULT_THINKING_LEVEL",
    "THINKING_LEVELS",
    "THINKING_LEVEL_DESCRIPTIONS",
    "ThinkingLevel",
    "anthropic_thinking_budget_for_level",
    "clear_thinking_level",
    "next_thinking_level",
    "normalize_thinking_level",
    "normalize_thinking_levels",
    "reasoning_effort_for_level",
    "set_thinking_level",
    "thinking_enabled",
    "thinking_level_from_env",
]

ThinkingLevel = Literal["off", "minimal", "low", "medium", "high", "xhigh"]
ReasoningEffort = Literal["none", "minimal", "low", "medium", "high", "xhigh"]

THINKING_LEVELS: tuple[ThinkingLevel, ...] = (
    "off",
    "minimal",
    "low",
    "medium",
    "high",
    "xhigh",
)
# Proofs run fastest with thinking off (the compile loop is the repair
# signal), so tactic defaults to "off" where tau defaults to "medium".
DEFAULT_THINKING_LEVEL: ThinkingLevel = "off"

THINKING_LEVEL_DESCRIPTIONS: dict[ThinkingLevel, str] = {
    "off": "No reasoning",
    "minimal": "Very brief reasoning",
    "low": "Light reasoning",
    "medium": "Moderate reasoning",
    "high": "Deep reasoning",
    "xhigh": "Maximum reasoning",
}

# Process-level override set via /thinking in the TUI (None = use the env).
_active_level: ThinkingLevel | None = None


def normalize_thinking_level(value: str | None) -> ThinkingLevel:
    """Return a valid thinking level or raise a user-facing error."""
    if value is None:
        return DEFAULT_THINKING_LEVEL
    normalized = value.strip().lower()
    if normalized in THINKING_LEVELS:
        return normalized
    allowed = ", ".join(THINKING_LEVELS)
    raise ValueError(f"Unknown thinking mode: {value}. Available modes: {allowed}")


def normalize_thinking_levels(values: Sequence[str]) -> tuple[ThinkingLevel, ...]:
    """Return a validated, duplicate-free thinking level tuple."""
    if isinstance(values, str) or not values:
        allowed = ", ".join(THINKING_LEVELS)
        raise ValueError(
            f"Thinking modes must be a non-empty list. Available modes: {allowed}"
        )

    normalized = tuple(normalize_thinking_level(value) for value in values)
    if len(set(normalized)) != len(normalized):
        raise ValueError("Thinking modes must be unique")
    return normalized


def reasoning_effort_for_level(level: str | None) -> ReasoningEffort:
    """Map a thinking level to an OpenAI-compatible reasoning effort."""
    normalized = normalize_thinking_level(level)
    if normalized == "off":
        return "none"
    return normalized


def anthropic_thinking_budget_for_level(level: str | None) -> int | None:
    """Map a thinking level to Anthropic extended-thinking tokens."""
    normalized = normalize_thinking_level(level)
    if normalized == "off":
        return None
    return {
        "minimal": 1024,
        "low": 2048,
        "medium": 4096,
        "high": 8192,
        "xhigh": 16384,
    }[normalized]


def next_thinking_level(
    current: str | None,
    *,
    available: tuple[ThinkingLevel, ...] = THINKING_LEVELS,
) -> ThinkingLevel:
    """Return the next thinking level in a stable cycle."""
    if not available:
        return DEFAULT_THINKING_LEVEL
    try:
        normalized_current = normalize_thinking_level(current)
        index = available.index(normalized_current)
    except ValueError:
        return available[0]
    return available[(index + 1) % len(available)]


def set_thinking_level(level: str | None) -> ThinkingLevel:
    """Set the process-level thinking override (TUI /thinking wiring).

    Returns the normalized level; the override wins over the environment
    until cleared with `clear_thinking_level()`.
    """
    global _active_level
    _active_level = normalize_thinking_level(level)
    return _active_level


def clear_thinking_level() -> None:
    """Drop the process override; env resolution applies again."""
    global _active_level
    _active_level = None


def thinking_level_from_env() -> ThinkingLevel:
    """Resolve the active thinking level from the override/environment.

    Precedence: process override (TUI) > TACTIC_THINKING >
    TACTIC_DISABLE_THINKING=1 (the legacy hard switch, on by default) >
    default. Explicit intent wins over the blanket default.
    """
    if _active_level is not None:
        return _active_level
    explicit = os.environ.get("TACTIC_THINKING")
    normalized = normalize_thinking_level(explicit) if explicit else None
    if normalized is not None and normalized != "off":
        return normalized
    if normalized is None and os.environ.get("TACTIC_DISABLE_THINKING", "1") == "1":
        return "off"
    return normalized or DEFAULT_THINKING_LEVEL


def thinking_enabled(level: ThinkingLevel | None = None) -> bool:
    """Whether the active level keeps provider thinking switched on."""
    resolved = level or thinking_level_from_env()
    return resolved != "off"

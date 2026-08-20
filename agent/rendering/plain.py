"""Plain-text conversation renderer — Tau rendering/plain.py port.

No colors, no Rich: just ``role: text`` lines with optional tool-call
annotation. Used for piped output and the ``--output text`` CLI path.
"""

from __future__ import annotations

from typing import Any

from .base import RenderOptions


def render_conversation_plain(messages: list[Any], options: RenderOptions | None = None) -> str:
    options = options or RenderOptions()
    out: list[str] = []
    for message in messages:
        role = getattr(message, "role", "message") if not isinstance(message, dict) else message.get("role", "message")
        text = _text_of(message)
        if role == "toolResult":
            if not options.show_tool_results:
                continue
            tool_name = getattr(message, "tool_name", None) if not isinstance(message, dict) else message.get("tool_name")
            if options.max_result_lines is not None:
                text = _limit_lines(text, options.max_result_lines)
            out.append(f"[tool:{tool_name or '?'}] {text}")
            continue
        if not text and not getattr(message, "tool_calls", None):
            continue
        if text:
            out.append(f"{role}: {text}")
        if options.show_tool_calls and getattr(message, "tool_calls", None):
            for tc in message.tool_calls:
                out.append(f"  -> tool call: {tc.name}")
    return "\n".join(out) + ("\n" if out else "")


def _text_of(message: Any) -> str:
    if isinstance(message, dict):
        return str(message.get("content", ""))
    return str(getattr(message, "text", "") or "")


def _limit_lines(text: str, limit: int) -> str:
    lines = text.splitlines()
    if len(lines) <= limit:
        return text
    return "\n".join(lines[:limit]) + f"\n[... {len(lines) - limit} more lines]"

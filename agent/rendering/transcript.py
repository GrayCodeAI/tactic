"""Markdown transcript renderer — Tau rendering/transcript.py port.

Renders a typed ``AgentMessage`` conversation as a markdown transcript:
user/assistant turns as fenced sections, tool calls as ``**tool** args``
lines with bounded result previews, thinking blocks optionally shown.

Rich is only imported for the terminal path; the markdown string itself is
dependency-free.
"""

from __future__ import annotations

from typing import Any

from .base import RenderOptions


def render_conversation_transcript(
    messages: list[Any], options: RenderOptions | None = None
) -> str:
    options = options or RenderOptions()
    out: list[str] = ["# Transcript", ""]
    for message in messages:
        role = _role_of(message)
        if role == "toolResult":
            if options.show_tool_results:
                tool_name = _attr(message, "tool_name") or "?"
                text = _text_of(message)
                err = " (error)" if _attr(message, "is_error") else ""
                out.append(f"**{tool_name}**{err}")
                out.append("> " + _indent_preview(text, 600))
                out.append("")
            continue
        text = _text_of(message)
        if role == "user":
            out.append(f"## User\n\n{text}\n")
        elif role == "assistant":
            if options.show_thinking:
                thinking = _attr(message, "thinking_text") or ""
                if thinking:
                    out.append(f"### Thinking\n\n> {_indent_preview(thinking, 800)}\n")
            if text:
                out.append(f"## Assistant\n\n{text}\n")
            if options.show_tool_calls and _attr(message, "tool_calls"):
                for tc in _attr(message, "tool_calls") or ():
                    out.append(f"- tool call: **{tc.name}**")
                out.append("")
        elif role == "compactionSummary":
            out.append(f"## Compaction\n\n{_attr(message, 'summary') or text}\n")
        elif role == "branchSummary":
            out.append(f"## Branch summary\n\n{_attr(message, 'summary') or text}\n")
        elif text:
            out.append(f"## {role}\n\n{text}\n")
    return "\n".join(out).rstrip() + "\n"


def _role_of(message: Any) -> str:
    if isinstance(message, dict):
        return str(message.get("role", "message"))
    return str(getattr(message, "role", "message"))


def _attr(message: Any, name: str) -> Any:
    if isinstance(message, dict):
        return message.get(name)
    return getattr(message, name, None)


def _text_of(message: Any) -> str:
    if isinstance(message, dict):
        return str(message.get("content", ""))
    return str(getattr(message, "text", "") or "")


def _indent_preview(text: str, max_chars: int) -> str:
    text = text.strip()
    if len(text) > max_chars:
        text = text[:max_chars] + " [...]"
    return text.replace("\n", "\n> ")

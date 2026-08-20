"""JSON conversation renderer — Tau rendering/json.py port.

Renders a typed ``AgentMessage`` conversation as a JSON lines transcript
(one object per message, pi-compatible), plus the flat prover event records.
"""

from __future__ import annotations

import json
from typing import Any

from .base import RenderOptions


def render_conversation_json(messages: list[Any], options: RenderOptions | None = None) -> str:
    """Serialize typed messages as JSON lines."""
    options = options or RenderOptions()
    lines: list[str] = []
    for message in messages:
        if hasattr(message, "role"):
            payload: dict[str, Any] = {
                "role": message.role,
                "text": getattr(message, "text", ""),
            }
            if options.show_tool_calls and getattr(message, "tool_calls", None):
                payload["tool_calls"] = [
                    {"name": tc.name, "arguments": tc.arguments}
                    for tc in message.tool_calls
                ]
            if getattr(message, "tool_name", None):
                payload["tool_name"] = message.tool_name
                payload["is_error"] = bool(getattr(message, "is_error", False))
        elif isinstance(message, dict):
            payload = message
        else:
            payload = {"content": str(message)}
        lines.append(json.dumps(payload, ensure_ascii=False, default=str))
    return "\n".join(lines) + ("\n" if lines else "")


def render_records_json(records: list[dict]) -> str:
    """Prover event records as JSON lines (delegates to events shapes)."""
    lines = [json.dumps(r, ensure_ascii=False, default=str) for r in records]
    return "\n".join(lines) + ("\n" if lines else "")

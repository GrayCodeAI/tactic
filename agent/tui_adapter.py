"""TUI event adapter — Tau tui/adapter.py port (Tau 37a9e43 src/tau_coding/tui/adapter.py).

Maps ``AgentEvent`` instances from the harness/run_agent_loop into chat
items the TUI can display, threading them through ``TuiState`` for
tool-call grouping. Emits neutral display records (text/role) so the TUI
layer keeps its own RichLog styling.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .events import (
    AgentEndEvent,
    AgentStartEvent,
    MessageEndEvent,
    MessageStartEvent,
    MessageUpdateEvent,
    ToolExecutionEndEvent,
    ToolExecutionStartEvent,
    ToolExecutionUpdateEvent,
    TurnEndEvent,
    TurnStartEvent,
)
from .tui_state import TuiState


@dataclass(frozen=True, slots=True)
class ChatItem:
    """One displayable transcript item (tau ChatItem analogue)."""

    kind: str  # text | tool_line | tool_update | error | system
    text: str
    style: str = ""
    payload: Any = None


class TuiEventAdapter:
    def __init__(self, state: TuiState | None = None) -> None:
        self.state = state or TuiState()
        self.items: list[ChatItem] = []

    def handle(self, event: Any) -> list[ChatItem]:
        """Consume one AgentEvent, returning newly created chat items."""
        new: list[ChatItem] = []
        if isinstance(event, (AgentStartEvent, TurnStartEvent)):
            self.state.start_turn()
        elif isinstance(event, MessageStartEvent):
            message = event.message
            text = getattr(message, "text", "") or ""
            role = getattr(message, "role", "message")
            if text and role in ("user", "assistant"):
                new.append(ChatItem(kind="text", text=text, style=role))
        elif isinstance(event, MessageUpdateEvent):
            message = event.message
            text = getattr(message, "text", "") or ""
            if text:
                new.append(ChatItem(kind="text", text=text, style="assistant-update"))
        elif isinstance(event, ToolExecutionStartEvent):
            display = self.state.add_tool_call(event.tool_call_id, event.tool_name, event.args)
            new.append(ChatItem(kind="tool_line", text=self.state.format_tool_call_invocation(display), payload=display))
        elif isinstance(event, ToolExecutionUpdateEvent):
            partial = event.partial_result
            text = getattr(partial, "content", "") or ""
            if isinstance(text, list):
                text = "".join(getattr(b, "text", "") for b in text)
            display = self.state.record_tool_update(event.tool_call_id, result_text=str(text or ""))
            if display is not None:
                new.append(ChatItem(kind="tool_update", text=self.state.result_preview(display), payload=display))
        elif isinstance(event, ToolExecutionEndEvent):
            text = event.result.content if isinstance(event.result.content, str) else "".join(
                getattr(b, "text", "") for b in event.result.content
            )
            status = "error" if event.is_error else "done"
            display = self.state.record_tool_update(event.tool_call_id, status=status, result_text=str(text or ""))
            if display is not None:
                item = ChatItem(
                    kind="tool_update",
                    text=self.state.format_tool_call_invocation(display),
                    style="error" if event.is_error else "success",
                    payload=display,
                )
                new.append(item)
        elif isinstance(event, TurnEndEvent):
            line = self.state.active_tool_line()
            if line:
                new.append(ChatItem(kind="tool_line", text=line, style="batch"))
        elif isinstance(event, AgentEndEvent):
            final = event.messages[-1] if event.messages else None
            error = getattr(final, "error_message", None) if final is not None else None
            if error:
                new.append(ChatItem(kind="error", text=str(error)))
        elif isinstance(event, MessageEndEvent):
            message = event.message
            if getattr(message, "is_error", False):
                new.append(ChatItem(kind="error", text=getattr(message, "text", "") or "error"))
        self.items.extend(new)
        return new

    def drain(self) -> list[ChatItem]:
        items = self.items
        self.items = []
        return items

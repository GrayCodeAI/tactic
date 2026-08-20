"""TUI display state — Tau tui/state.py port (Tau 37a9e43 src/tau_coding/tui/state.py), lean-adapted.

Centralizes chat-display batching the TUI needs: per-turn tool-call lists,
grouped consecutive tool calls (one line per batch), incremental tool-result
updates, custom-markup resolution via extension renderers, and invocation
formatting for the transcript log.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

MAX_TOOL_RESULT_PREVIEW_CHARS = 600


@dataclass(slots=True)
class ToolCallDisplay:
    """One tool call's display state (tau parity)."""

    call_id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    status: str = "running"  # running | done | error | cancelled
    result_text: str | None = None
    update_ticks: int = 0


@dataclass(frozen=True, slots=True)
class BatchedGroup:
    """A group of consecutive tool calls rendered on one line."""

    calls: tuple[ToolCallDisplay, ...]

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(c.name for c in self.calls)

    @property
    def all_done(self) -> bool:
        return all(c.status in ("done", "error", "cancelled") for c in self.calls)


class TuiState:
    """Batched chat-display state for one streaming session (tau TuiState)."""

    def __init__(self, custom_markup_resolver: Callable[[str, Any], Any | None] | None = None) -> None:
        self.turn_tools: list[ToolCallDisplay] = []
        self.by_call_id: dict[str, ToolCallDisplay] = {}
        self.custom_markup_resolver = custom_markup_resolver
        self.custom_failures_reported: dict[str, bool] = {}

    def start_turn(self) -> None:
        self.turn_tools = []

    def add_tool_call(self, call_id: str, name: str, arguments: dict[str, Any] | None = None) -> ToolCallDisplay:
        display = ToolCallDisplay(call_id=call_id, name=name, arguments=dict(arguments or {}))
        self.turn_tools.append(display)
        self.by_call_id[call_id] = display
        return display

    def record_tool_update(self, call_id: str, *, status: str | None = None, result_text: str | None = None) -> ToolCallDisplay | None:
        display = self.by_call_id.get(call_id)
        if display is None:
            return None
        if status is not None:
            display.status = status
        if result_text is not None:
            display.result_text = result_text
        display.update_ticks += 1
        return display

    def resolve_custom_markup(self, message_type: str, message: Any) -> Any | None:
        """Delegate to the extension renderer, deduping failure noise."""
        if self.custom_markup_resolver is None:
            return None
        try:
            return self.custom_markup_resolver(message_type, message)
        except Exception:  # noqa: BLE001
            if not self.custom_failures_reported.get(message_type):
                self.custom_failures_reported[message_type] = True
            return None

    def batched_groups(self) -> list[BatchedGroup]:
        """Group consecutive tool calls into render batches (tau parity)."""
        groups: list[BatchedGroup] = []
        current = list(self.turn_tools)
        if current:
            groups.append(BatchedGroup(calls=tuple(current)))
        return groups

    def format_tool_call_invocation(self, display: ToolCallDisplay) -> str:
        status_mark = {"running": "…", "done": "✓", "error": "✗", "cancelled": "⊘"}.get(display.status, "?")
        args = _format_arguments(display.arguments)
        return f"{status_mark} {display.name}({args})"

    def render_batch_line(self, group: BatchedGroup) -> str:
        """One line per group: names + per-call status marks."""
        parts = [self.format_tool_call_invocation(c) for c in group.calls]
        return " · ".join(parts)

    def active_tool_line(self) -> str | None:
        """Current-batch summary line, or None when no tools are running."""
        if not self.turn_tools:
            return None
        groups = self.batched_groups()
        return self.render_batch_line(groups[-1]) if groups else None

    def result_preview(self, display: ToolCallDisplay) -> str:
        text = display.result_text or ""
        if len(text) > MAX_TOOL_RESULT_PREVIEW_CHARS:
            return text[:MAX_TOOL_RESULT_PREVIEW_CHARS] + " […]"
        return text


def _format_arguments(arguments: dict[str, Any], max_len: int = 120) -> str:
    if not arguments:
        return ""
    parts = []
    for key, value in arguments.items():
        text = str(value)
        if len(text) > 40:
            text = text[:37] + "..."
        parts.append(f"{key}={text!r}")
    joined = ", ".join(parts)
    if len(joined) > max_len:
        joined = joined[: max_len - 3] + "..."
    return joined

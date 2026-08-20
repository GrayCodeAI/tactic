"""Session entry tree — Tau session/entries.py port (Tau 37a9e43 src/tau_agent/session/entries.py), lean-adapted."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

JSONValue: Any = Any


@dataclass
class SessionEntry:
    entry_id: str = ""
    type: str = "message"
    timestamp: str = ""
    role: str = ""
    content: str = ""
    tool_call_id: str | None = None
    tool_name: str | None = None
    tool_arguments: str | None = None
    is_error: bool = False
    summary: str = ""
    compacted_entry_ids: tuple[str, ...] = ()
    parent_entry_id: str | None = None
    kind: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    label: str = ""
    message_entry_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"id": self.entry_id, "type": self.type}
        if self.timestamp:
            d["timestamp"] = self.timestamp
        if self.role:
            d["role"] = self.role
        if self.content:
            d["content"] = self.content
        if self.tool_call_id is not None:
            d["tool_call_id"] = self.tool_call_id
        if self.tool_name is not None:
            d["tool_name"] = self.tool_name
        if self.tool_arguments is not None:
            d["tool_arguments"] = self.tool_arguments
        if self.is_error:
            d["is_error"] = True
        if self.summary:
            d["summary"] = self.summary
        if self.compacted_entry_ids:
            d["compacted_entry_ids"] = list(self.compacted_entry_ids)
        if self.parent_entry_id is not None:
            d["parent_entry_id"] = self.parent_entry_id
        if self.kind:
            d["kind"] = self.kind
        if self.payload:
            d["payload"] = self.payload
        if self.label:
            d["label"] = self.label
        if self.message_entry_id is not None:
            d["message_entry_id"] = self.message_entry_id
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionEntry:
        return cls(
            entry_id=str(data.get("id") or ""),
            type=str(data.get("type") or "message"),
            timestamp=str(data.get("timestamp") or ""),
            role=str(data.get("role") or ""),
            content=str(data.get("content") or ""),
            tool_call_id=data.get("tool_call_id"),
            tool_name=data.get("tool_name"),
            tool_arguments=data.get("tool_arguments"),
            is_error=bool(data.get("is_error", False)),
            summary=str(data.get("summary") or ""),
            compacted_entry_ids=tuple(str(x) for x in (data.get("compacted_entry_ids") or [])),
            parent_entry_id=data.get("parent_entry_id"),
            kind=str(data.get("kind") or ""),
            payload=data.get("payload") if isinstance(data.get("payload"), dict) else {},
            label=str(data.get("label") or ""),
            message_entry_id=data.get("message_entry_id"),
        )
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ToolHistoryRepair:
    messages: tuple[dict, ...]
    changed: bool = False
    synthesized_results: int = 0


def repair_tool_history(messages) -> ToolHistoryRepair:  # type: ignore[no-untyped-def]
    if messages and not isinstance(messages[0], dict):
        return ToolHistoryRepair(messages=tuple(messages), changed=False)
    seen_ids: set[str] = set()
    for m in messages:
        for tc in m.get("tool_calls", []) if isinstance(m.get("tool_calls"), list) else []:
            seen_ids.add(tc.get("id", ""))

    repaired: list[dict] = []
    synthesized = 0
    for m in messages:
        repaired.append(m)
        if m.get("role") == "assistant" and m.get("tool_calls"):
            for tc in m["tool_calls"]:
                tid = tc.get("id", "")
                has_result = any(
                    n.get("role") == "tool" and n.get("tool_call_id") == tid for n in messages
                )
                if not has_result and tid:
                    repaired.append({"role": "tool", "tool_call_id": tid, "content": "Tool call interrupted by user", "is_error": True})
                    synthesized += 1
    changed = len(repaired) != len(messages)
    return ToolHistoryRepair(messages=tuple(repaired), changed=changed, synthesized_results=synthesized)

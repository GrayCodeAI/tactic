"""Event protocol for the proof loop.

Every state change in `loop.prove()` flows through a single `emit()` path as
a self-describing record:

    {"t": 1730000000.123, "event": "build", "step": 3, "diagnostics": 2, ...}

Three consumers, one stream:
- `trace`   — kept in memory, embedded in Result and report JSON
- session   — JSONL under ~/.tactic/sessions/ (agent/session.py)
- `on_event` — live callback (TUI), see agent/tui.py

The CLI renders records with `format()`; the TUI renders the same records in
its own way. The loop itself prints nothing.
"""

from __future__ import annotations

import time


def record(event: str, **payload) -> dict:
    """Build a self-describing event record."""
    return {"t": time.time(), "event": event, **payload}


def format(rec: dict) -> str | None:
    """Human-readable line for a record, or None if it shouldn't be printed."""
    ev = rec.get("event")
    if ev == "start":
        stmt = rec.get("statement", "")
        return f"start: {rec.get('problem_id', '?')} (max_steps={rec.get('max_steps')}) {str(stmt)[:70]}"
    if ev == "hammer":
        mark = "✓" if rec.get("ok") else "✗"
        return f"  [hammer {rec['i']}/{rec['total']}] `{rec['tactic']}` {mark}"
    if ev == "llm_start":
        return "  no hammer worked, starting LLM loop"
    if ev == "build":
        if rec.get("ok"):
            return None  # the proved record carries the good news
        summary = str(rec.get("summary", ""))[:70]
        return f"  [step {rec['step']}] {rec['diagnostics']} diagnostics — {summary}"
    if ev == "goals":
        first = str(rec.get("goals", "")).strip().splitlines()
        return f"  [step {rec['step']}] goal: {first[0] if first else ''}"
    if ev == "llm_request":
        return None
    if ev == "llm_response":
        return f"  [step {rec['step']}] LLM replied ({rec.get('tokens', '?')} tokens)"
    if ev == "llm_error":
        return f"  [step {rec['step']}] {str(rec.get('error', ''))[:100]}"
    if ev == "result":
        secs = rec.get("seconds", 0.0)
        steps = rec.get("steps", 0)
        if rec.get("stopped"):
            return f"  stopped by user ({secs:.1f}s)"
        if rec.get("proved"):
            return f"  PROVED ∎ ({steps} steps, {secs:.1f}s)"
        return f"  FAILED after {steps} steps ({secs:.1f}s)"
    return None

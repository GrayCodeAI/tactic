"""Output-mode renderers for the proof loop (tau rendering package port).

Tau splits print output into three renderers — final text, JSON event stream,
and a streaming transcript.  Prover flattens the package into one module and
adapts tau's typed `CodingSessionEvent`s to prover's dict event records
(agent/events.py):

- `text`       — FinalTextRenderer: print only the final proof body (or error)
- `json`       — JsonEventRenderer: one JSON object per record (pi-compatible)
- `transcript` — TranscriptRenderer: human-readable colored stream

`create_event_renderer(mode)` picks one; every renderer implements tau's
`EventRenderer` protocol (`render(record)` / `finish() -> bool`).
"""

from __future__ import annotations

import json
import sys
from enum import StrEnum
from typing import Protocol

from .. import events

__all__ = [
    "EventRenderer",
    "FinalTextRenderer",
    "JsonEventRenderer",
    "PrintOutputMode",
    "TranscriptRenderer",
    "create_event_renderer",
]


class PrintOutputMode(StrEnum):
    """Output modes supported by non-interactive prove runs (tau's PrintOutputMode)."""

    text = "text"
    json = "json"
    transcript = "transcript"


class EventRenderer(Protocol):
    """Consumes proof-loop event records and renders them (tau's EventRenderer)."""

    def render(self, record: dict) -> None:
        """Render one event record."""
        ...

    def finish(self) -> bool:
        """Finish rendering and return whether the run succeeded."""
        ...


def create_event_renderer(mode: PrintOutputMode | str) -> EventRenderer:
    """Create a renderer for a print output mode."""
    if mode == PrintOutputMode.text:
        return FinalTextRenderer()
    if mode == PrintOutputMode.json:
        return JsonEventRenderer()
    if mode == PrintOutputMode.transcript:
        return TranscriptRenderer()
    allowed = ", ".join(m.value for m in PrintOutputMode)
    raise ValueError(f"Unknown output mode: {mode}. Available modes: {allowed}")


def _print(text: str, *, err: bool = False) -> None:
    stream = sys.stderr if err else sys.stdout
    stream.write(text + "\n")


class JsonEventRenderer:
    """Pi-compatible JSON event stream: one JSON object per record."""

    def __init__(self) -> None:
        self._failed = False

    def render(self, record: dict) -> None:
        if record.get("event") == "result" and not record.get("proved"):
            self._failed = True
        _print(json.dumps(record, ensure_ascii=False, default=str))

    def finish(self) -> bool:
        return not self._failed


class FinalTextRenderer:
    """Print only the final outcome: the proof text on success, errors on failure."""

    def __init__(self) -> None:
        self._failed = False
        self._stopped = False
        self._error_messages: list[str] = []
        self._last_body: str | None = None

    def render(self, record: dict) -> None:
        ev = record.get("event")
        if ev == "llm_response":
            body = str(record.get("body") or "")
            if body.strip():
                self._last_body = body
        elif ev == "llm_error":
            self._error_messages.append(str(record.get("error") or "Error"))
        elif ev == "result":
            self._failed = not record.get("proved")
            self._stopped = bool(record.get("stopped"))

    def finish(self) -> bool:
        if self._failed:
            if self._stopped and not self._error_messages:
                _print("Error: stopped by user", err=True)
            for message in self._error_messages:
                _print(f"Error: {message}", err=True)
            if not self._error_messages and not self._stopped:
                _print("Error: proof not type-checked within the step budget", err=True)
            return False
        if self._last_body:
            _print(self._last_body)
        return True


class TranscriptRenderer:
    """Human-readable streaming transcript of the proof run."""

    def __init__(self) -> None:
        self._failed = False

    def render(self, record: dict) -> None:
        line = events.format(record)
        if line is None:
            return
        style = _style_for(record.get("event"))
        if style:
            _print(f"\x1b[{style}m{line}\x1b[0m")
        else:
            _print(line)
        if record.get("event") == "result" and not record.get("proved"):
            self._failed = True

    def finish(self) -> bool:
        return not self._failed


_STYLES = {
    "start": "1;35",    # bold magenta
    "resume": "1;32",   # bold green
    "hammer": "34",     # blue
    "build": "33",      # yellow
    "goals": "35",      # magenta
    "compaction": "33", # yellow
    "llm_response": "36",
    "llm_error": "31",  # red
    "result": "1;32",   # bold green (FAILED text goes through the same line)
}


def _style_for(event: str | None) -> str | None:
    return _STYLES.get(event or "")

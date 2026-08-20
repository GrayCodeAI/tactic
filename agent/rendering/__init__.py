"""Renderers — Tau rendering package port, lean-adapted.

Two renderer families:

* Typed-conversation renderers (Tau parity): ``RenderOptions`` +
  json / plain / transcript over ``AgentMessage`` lists.
* Prover-loop event renderers (existing): ``create_event_renderer``
  over flat dict event records — re-exported from ``rendering.events``.
"""

from __future__ import annotations

from .base import RenderOptions
from .events import (
    EventRenderer,
    FinalTextRenderer,
    JsonEventRenderer,
    PrintOutputMode,
    TranscriptRenderer,
    create_event_renderer,
)
from .json import render_conversation_json, render_records_json
from .plain import render_conversation_plain
from .transcript import render_conversation_transcript

__all__ = [
    "EventRenderer",
    "FinalTextRenderer",
    "JsonEventRenderer",
    "PrintOutputMode",
    "RenderOptions",
    "TranscriptRenderer",
    "create_event_renderer",
    "render_conversation_json",
    "render_conversation_plain",
    "render_conversation_transcript",
    "render_records_json",
]

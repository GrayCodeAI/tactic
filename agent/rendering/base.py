"""Render options — Tau rendering/base.py port (Tau 37a9e43 src/tau_coding/rendering/base.py)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RenderOptions:
    """Knobs shared by all transcript renderers (tau RenderOptions)."""

    show_tool_calls: bool = True
    show_tool_results: bool = True
    show_thinking: bool = False
    max_result_lines: int | None = None
    colors: bool = True
    width: int | None = None

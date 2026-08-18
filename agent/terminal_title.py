"""Terminal title + activity indicator controller
(ported from huggingface/tau tui/terminal_title.py).

The TUI reflects run state in the terminal tab title: a bare "τ" mark when
idle, and a spinning braille frame prefixed while a proof run is active.
Writes dedupe (only emit the OSC sequence when the title actually changes),
and any write failure disables further writes so a broken stream never
interleaves escape codes with output.
"""

from __future__ import annotations

import os
import sys

MAX_TERMINAL_TITLE_LENGTH = 120
TAU_TITLE_MARK = "τ"

# Same braille spinner frames tau uses for the running state.
RUNNING_TITLE_FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")


def terminal_title_supported() -> bool:
    """Respect no-title env / dumb terminal / non-tty (tau parity)."""
    flag = os.environ.get("PROVER_TERMINAL_TITLE", "")
    if flag.lower() in ("0", "false", "no", "off"):
        return False
    if flag == "1":
        return True  # force on (e.g. in CI)
    if os.environ.get("TERM") == "dumb":
        return False
    if os.environ.get("CI"):
        return False
    try:
        return sys.stdout.isatty()
    except (AttributeError, ValueError):
        return False


def sanitize_terminal_title(value: str) -> str:
    """Strip control bytes and cap length with an ellipsis (tau parity)."""
    cleaned = "".join(ch for ch in value if ord(ch) >= 32 and ch != "\x7f")
    if len(cleaned) > MAX_TERMINAL_TITLE_LENGTH:
        cleaned = cleaned[: MAX_TERMINAL_TITLE_LENGTH - 1] + "…"
    return cleaned


def build_terminal_title(session_title: str | None, *, running: bool = False,
                         frame: int = 0) -> str:
    """Compose the title string (tau's build_terminal_title)."""
    title = sanitize_terminal_title(session_title or "").strip()
    base = f"{TAU_TITLE_MARK} | {title}" if title else TAU_TITLE_MARK
    if running:
        spinner = RUNNING_TITLE_FRAMES[frame % len(RUNNING_TITLE_FRAMES)]
        return f"{spinner} {base}"
    return base


def osc_terminal_title_sequence(title: str) -> str:
    """OSC 0 title escape sequence (tau parity)."""
    return f"\x1b]0;{title}\x07"


class TerminalTitleController:
    """Stateful writer; dedupes, disables itself on failure (tau parity)."""

    def __init__(self) -> None:
        self._last_title: str | None = None
        self._disabled = False

    def update(self, session_title: str | None, *, running: bool = False,
               frame: int = 0) -> None:
        if self._disabled or not terminal_title_supported():
            return
        title = build_terminal_title(session_title, running=running, frame=frame)
        if title == self._last_title:
            return
        self._last_title = title
        try:
            sys.stdout.write(osc_terminal_title_sequence(title))
            sys.stdout.flush()
        except (OSError, ValueError):
            self._disabled = True

    def restore(self) -> None:
        """Reset to the bare mark on shutdown (tau parity)."""
        if self._disabled or not terminal_title_supported():
            return
        self._last_title = None
        try:
            sys.stdout.write(osc_terminal_title_sequence(TAU_TITLE_MARK))
            sys.stdout.flush()
        except (OSError, ValueError):
            self._disabled = True

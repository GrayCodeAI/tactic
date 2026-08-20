"""Slash-command autocomplete (ported from huggingface/tau tui/autocomplete.py).

Textual-native simplification of tau's CompletionItem/CompletionState: we
complete slash-command prefixes (`/mo` → `/model`, `/exit`, `/quit`…) and
session ids (`/resume 2026…` → recorded session stems).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .commands import CommandRegistry, SlashCommand


@dataclass(frozen=True, slots=True)
class CompletionItem:
    """One completion candidate (tau CompletionItem)."""

    text: str
    description: str = ""
    kind: str = "command"  # command | session


@dataclass
class CompletionState:
    """Tracks the active completion candidates + selection index (tau parity)."""

    items: list[CompletionItem] | None = None
    index: int = 0

    @property
    def active(self) -> bool:
        return bool(self.items)

    @property
    def current(self) -> CompletionItem | None:
        if not self.items:
            return None
        return self.items[min(self.index, len(self.items) - 1)]

    def set_items(self, items: list[CompletionItem]) -> None:
        self.items = items or None
        self.index = 0

    def next(self) -> CompletionItem | None:
        if not self.items:
            return None
        self.index = (self.index + 1) % len(self.items)
        return self.current

    def previous(self) -> CompletionItem | None:
        if not self.items:
            return None
        self.index = (self.index - 1) % len(self.items)
        return self.current

    def clear(self) -> None:
        self.items = None
        self.index = 0


def build_completion_state(
    registry: CommandRegistry,
    text: str,
    session_ids: Sequence[str] = (),
    max_items: int = 8,
) -> CompletionState:
    """Build a completion state for the current prompt text (tau parity).

    Handles slash-command prefixes and session-id suffixes (``/resume 2026…``
    completes recorded session stems).
    """
    state = CompletionState()
    stripped = text.strip()
    if stripped.startswith(("/resume ", "/fork ", "/branch ")):
        _, _, partial = stripped.partition(" ")
        partial = partial.strip().lower()
        matches = [s for s in session_ids if s.lower().startswith(partial)]
        state.set_items(
            [CompletionItem(text=s, description="session", kind="session") for s in matches[:max_items]]
        )
        return state
    pairs = command_completions(registry, text, max_items=max_items)
    state.set_items([CompletionItem(text=t, description=d, kind="command") for t, d in pairs])
    return state


def command_completions(
    registry: CommandRegistry, text: str, max_items: int = 8
) -> list[tuple[str, str]]:
    """Completion candidates for partial slash-command input.

    Only active when the text starts with `/` and has no space yet.
    Returns (replacement, description) tuples. Tau's ordering: command
    names and aliases that match the prefix rank as direct matches sorted
    by display name; search-term matches come after, also sorted.
    """
    stripped = text.strip()
    if not stripped.startswith("/") or " " in stripped:
        return []
    prefix = stripped.lstrip("/").lower()
    direct: list[tuple[str, str]] = []
    by_search: list[tuple[str, str]] = []
    seen: set[str] = set()
    for command in registry.list_commands():
        for display, description in _alias_completions(command):
            if display not in seen and display.removeprefix("/").lower().startswith(prefix):
                direct.append((display, description))
                seen.add(display)
        for term in command.search_terms:
            if (
                term.lower().startswith(prefix)
                and f"/{command.name}" not in seen
            ):
                by_search.append((f"/{command.name}", f"{command.description} [{term}]"))
                seen.add(f"/{command.name}")
    direct.sort(key=lambda item: item[0])
    by_search.sort(key=lambda item: item[0])
    return (*direct, *by_search)[:max_items]


def _alias_completions(command: SlashCommand) -> list[tuple[str, str]]:
    """(display, description) for a command and its aliases."""
    out = [(f"/{command.name}", command.description)]
    out.extend((f"/{alias}", f"alias of /{command.name}") for alias in command.aliases)
    return sorted(out, key=lambda item: item[0])


__all__: Sequence[str] = [
    "CompletionItem",
    "CompletionState",
    "build_completion_state",
    "command_completions",
]

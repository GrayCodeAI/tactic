"""Slash-command autocomplete (ported from huggingface/tau tui/autocomplete.py).

Textual-native simplification of tau's CompletionItem/CompletionState: we only
complete slash-command prefixes (`/mo` → `/model`, `/exit`, `/quit`…). The
result is a list of (replacement, description) tuples the prompt UI can render.
"""

from __future__ import annotations

from collections.abc import Sequence

from .commands import CommandRegistry, SlashCommand


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


__all__: Sequence[str] = ["command_completions"]

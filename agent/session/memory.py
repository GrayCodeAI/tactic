"""In-memory session storage — Tau session/memory.py port (tests, previews)."""

from __future__ import annotations

from .entries import SessionEntry


class InMemoryStorage:
    """A SessionStorage-compatible store that never touches disk."""

    def __init__(self) -> None:
        self._entries: list[SessionEntry] = []

    async def append(self, entries: list[SessionEntry]) -> None:
        self._entries.extend(entries)

    async def read_all(self) -> list[SessionEntry]:
        return list(self._entries)

    async def close(self) -> None:
        pass

"""Storage protocol + JSONL storage — Tau session/storage.py port.

Tau's ``SessionStorage`` is an async append/read-all protocol with atomic
``mkdir``; prover's legacy ``agent/session.py`` is sync caller-owned.  We
provide both: the async protocol (used by ``CodingSession``) and the sync
``JsonlSessionStorage`` (used by the flat JSONL path).
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from .entries import SessionEntry
from .jsonl import entries_from_json_lines, entry_to_json_line


class SessionStorage(Protocol):
    """Async storage for an ordered list of session entries."""

    async def append(self, entries: list[SessionEntry]) -> None:
        ...

    async def read_all(self) -> list[SessionEntry]:
        ...

    async def close(self) -> None:
        ...


class JsonlSessionStorage:
    """Append-only JSONL storage at a file path (atomic mkdir)."""

    def __init__(self, path: Path) -> None:
        self.path = path

    async def append(self, entries: list[SessionEntry]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as file:
            for entry in entries:
                file.write(entry_to_json_line(entry) + "\n")

    async def read_all(self) -> list[SessionEntry]:
        if not self.path.exists():
            return []
        return entries_from_json_lines(self.path.read_text(encoding="utf-8").splitlines())

    async def close(self) -> None:
        pass

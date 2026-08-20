"""JSONL codec for session entries — Tau session/jsonl.py port.

Uses ``splitlines()`` (handles U+2028/2029 as Tau documents) and round-trips
via ``json.dumps`` with ``ensure_ascii=False``.
"""

from __future__ import annotations

import json
from collections.abc import Iterable

from .entries import SessionEntry


def entry_to_json_line(entry: SessionEntry) -> str:
    """Serialize one entry as a single JSONL line."""
    return json.dumps(entry.to_dict(), ensure_ascii=False)


def entries_from_json_lines(lines: Iterable[str]) -> list[SessionEntry]:
    """Parse JSONL text lines into typed entries (skips blank/corrupt lines)."""
    entries: list[SessionEntry] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, dict):
            entries.append(SessionEntry.from_dict(data))
    return entries

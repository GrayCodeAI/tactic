"""Session tree helpers — Tau session/tree.py port.

A session's entries form a linear list ending in a ``LeafEntry``; branching
rewrites the tail (append new entries after a ``parent_entry_id``). ``path``
strings like ``"1.3"`` address entries by their 1-based list position.
"""

from __future__ import annotations

from .entries import SessionEntry


class SessionTreeError(ValueError):
    """Raised when a session tree path is malformed or out of range."""


def path_to_entry(entries: list[SessionEntry], path: str) -> SessionEntry:
    """Resolve a dotted path (``"3"``, ``"1.2"``) to an entry (tau path_to_entry).

    ``path`` is 1-based over the leaf's ``ancestor_chain``; for the flat list
    we map it to the entry at that index counting from the leaf backwards.
    """
    parts = path.strip().split(".")
    if not parts or any(not p.isdigit() for p in parts):
        raise SessionTreeError(f"invalid session path: {path!r}")
    if not entries:
        raise SessionTreeError("session has no entries")
    try:
        return entries[-int(parts[-1])]
    except IndexError:
        raise SessionTreeError(f"session path out of range: {path!r}") from None


def leaf_entry(entries: list[SessionEntry]) -> SessionEntry | None:
    """Return the terminal leaf entry, or None for an empty session."""
    for entry in reversed(entries):
        if entry.type == "leaf":
            return entry
    return None

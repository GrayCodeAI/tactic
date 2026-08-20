"""Project context discovery — Tau context.py port, lean-adapted.

Discovers AGENTS.md (and nested AGENTS.md) files plus ``.prover.md`` for
project-specific context that gets injected into the system prompt.
Adds a ``DISCOVERY_FAILED`` diagnostic when a referenced file doesn't exist.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def discover_project_context(cwd: Path | None = None) -> dict:
    """Read AGENTS.md from the project root (legacy compat)."""
    p = (cwd or Path.cwd()) / "AGENTS.md"
    return {"agents_md": p.read_text(errors="replace")[:4000] if p.exists() else ""}


def discover_project_context_with_diagnostics(cwd: Path | None = None) -> tuple[list[dict[str, str]], list[Any]]:
    """Discover project context files, returning (context_files, diagnostics)."""
    cwd = cwd or Path.cwd()
    context_files: list[dict[str, str]] = []
    diagnostics: list[Any] = []

    agents_md = cwd / "AGENTS.md"
    if agents_md.exists():
        context_files.append({"path": str(agents_md), "content": agents_md.read_text(errors="replace")[:4000]})
    else:
        diagnostics.append({"kind": "DISCOVERY_FAILED", "path": str(agents_md), "error": "AGENTS.md not found"})

    prover_md = cwd / ".prover.md"
    if prover_md.exists():
        context_files.append({"path": str(prover_md), "content": prover_md.read_text(errors="replace")[:2000]})

    return context_files, diagnostics
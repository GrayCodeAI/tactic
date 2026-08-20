from __future__ import annotations

from pathlib import Path


def discover_project_context(cwd: Path | None = None) -> dict:
    p = (cwd or Path.cwd()) / "AGENTS.md"
    return {"agents_md": p.read_text(errors="replace")[:4000] if p.exists() else ""}

"""Resource path discovery — Tau resources.py port, lean-adapted.

``TauResourcePaths`` collects all the directories the agent needs to discover
skills, templates, themes, and extensions.  Discovery follows project-local
first (``.prover/<kind>``), then user-level (``ProverPaths().<kind>_dir``),
then builtin (tied to the package).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .paths import ProverPaths


@dataclass(frozen=True, slots=True)
class TauResourcePaths:
    """Resolved resource directories (tau TauResourcePaths)."""

    skills_dirs: tuple[Path, ...] = ()
    templates_dirs: tuple[Path, ...] = ()
    themes_dirs: tuple[Path, ...] = ()
    extensions_dirs: tuple[Path, ...] = ()

    @property
    def all_dirs(self) -> tuple[Path, ...]:
        return self.skills_dirs + self.templates_dirs + self.themes_dirs


def discover_resources(cwd: Path | None = None) -> TauResourcePaths:
    cwd = cwd or Path.cwd()
    paths = ProverPaths()
    project = cwd / ".prover"
    return TauResourcePaths(
        skills_dirs=(project / "skills", paths.agents_home / "skills", ProverPaths().config_dir / "skills"),
        templates_dirs=(project / "prompts", paths.config_dir / "prompts"),
        themes_dirs=(project / "themes", paths.config_dir / "themes"),
        extensions_dirs=(project / "extensions", paths.config_dir / "extensions"),
    )


def discover_system_prompt_resources(cwd: Path | None = None) -> dict[str, Path | None]:
    """Discover AGENTS.md and .prover.md context files (tau parity)."""
    cwd = cwd or Path.cwd()
    return {
        "agents_md": cwd / "AGENTS.md" if (cwd / "AGENTS.md").exists() else None,
        "prover_md": cwd / ".prover.md" if (cwd / ".prover.md").exists() else None,
    }
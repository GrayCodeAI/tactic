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

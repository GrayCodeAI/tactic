"""Canonical filesystem paths for prover user and project data (tau paths.py port).

All env overrides funnel through `ProverPaths` so dir plumbing lives in one
place.  Precedence: `PROVER_*_DIR` env var > `PROVER_CONFIG_DIR` override >
`~/.prover` default.  Project resources are `Path.cwd()/.prover/<kind>` and
win over user-level ones (existing prompt-template behavior preserved).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ProverPaths:
    """Resolved prover filesystem locations."""

    home: Path = field(default_factory=lambda: Path.home() / ".prover")
    agents_home: Path = field(default_factory=lambda: Path.home() / ".agents")

    @property
    def config_dir(self) -> Path:
        """Dir holding all durable user data (PROVER_CONFIG_DIR overrides home)."""
        override = os.environ.get("PROVER_CONFIG_DIR")
        return Path(override) if override else self.home

    @property
    def sessions_dir(self) -> Path:
        """User-level proof session records."""
        override = os.environ.get("PROVER_SESSIONS_DIR")
        return Path(override) if override else self.home / "sessions"

    @property
    def prompts_dir(self) -> Path:
        """User-level prompt templates."""
        override = os.environ.get("PROVER_PROMPTS_DIR")
        return Path(override) if override else self.config_dir / "prompts"

    @property
    def themes_dir(self) -> Path:
        """User-level TUI themes."""
        override = os.environ.get("PROVER_THEMES_DIR")
        return Path(override) if override else self.config_dir / "themes"

    @property
    def logs_dir(self) -> Path:
        """User-level diagnostic log directory."""
        override = os.environ.get("PROVER_LOGS_DIR")
        return Path(override) if override else self.config_dir / "logs"

    @property
    def project_prompts_dir(self) -> Path:
        """Project-local prompt templates (cwd wins over user level)."""
        return Path.cwd() / ".prover" / "prompts"

    @property
    def project_themes_dir(self) -> Path:
        """Project-local TUI themes."""
        return Path.cwd() / ".prover" / "themes"
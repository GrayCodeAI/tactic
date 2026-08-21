"""Canonical filesystem paths — Tau paths.py extension, lean-adapted.

Adds ``TauPaths`` (XDG-style, ``~/.tau``) alongside the existing
``ProverPaths`` (``~/.prover``).  Both coexist so lean's prover path and
Tau's generic path can be used from the same process.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ProverPaths:
    home: Path = field(default_factory=lambda: Path.home() / ".prover")
    agents_home: Path = field(default_factory=lambda: Path.home() / ".agents")

    @property
    def config_dir(self) -> Path:
        override = os.environ.get("PROVER_CONFIG_DIR")
        return Path(override) if override else self.home

    @property
    def sessions_dir(self) -> Path:
        override = os.environ.get("PROVER_SESSIONS_DIR")
        return Path(override) if override else self.home / "sessions"

    @property
    def prompts_dir(self) -> Path:
        override = os.environ.get("PROVER_PROMPTS_DIR")
        return Path(override) if override else self.config_dir / "prompts"

    @property
    def themes_dir(self) -> Path:
        override = os.environ.get("PROVER_THEMES_DIR")
        return Path(override) if override else self.config_dir / "themes"

    @property
    def logs_dir(self) -> Path:
        override = os.environ.get("PROVER_LOGS_DIR")
        return Path(override) if override else self.config_dir / "logs"

    @property
    def project_prompts_dir(self) -> Path:
        return Path.cwd() / ".prover" / "prompts"


@dataclass(frozen=True, slots=True)
class TauPaths:
    """XDG-style generic agent paths (tau TauPaths)."""

    home: Path = field(default_factory=lambda: Path.home() / ".tau")
    config_dir: Path = field(default_factory=lambda: Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "tau")

    @property
    def sessions_dir(self) -> Path:
        return self.home / "sessions"

    @property
    def logs_dir(self) -> Path:
        return self.home / "logs"

    @property
    def credentials_path(self) -> Path:
        return self.home / "credentials"

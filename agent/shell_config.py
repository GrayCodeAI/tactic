"""Shell/bash tool configuration — Tau shell_config.py port, lean-adapted.

Controls the shell prefix injected into bash tool commands (e.g.,
``source .venv/bin/activate &&``) and the default shell binary.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ShellConfig:
    shell: str = ""
    prefix: str = ""
    timeout: int = 120

    @property
    def effective_shell(self) -> str:
        return self.shell or os.environ.get("SHELL", "/bin/bash")

    @property
    def effective_prefix(self) -> str:
        return self.prefix or os.environ.get("PROVER_SHELL_PREFIX", "")


def load_shell_config(path: str | None = None) -> ShellConfig:
    return ShellConfig()


def get_shell_prefix() -> str:
    override = os.environ.get("PROVER_SHELL_PREFIX")
    if override is not None:
        return override
    return ""
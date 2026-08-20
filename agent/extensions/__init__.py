"""Extensions — Tau extensions package port, lean-adapted.

Public surface: ``Extension``, ``discover_extensions`` (legacy discovery),
``load_extensions`` (async import + setup), ``ExtensionRuntime``,
``ExtensionContext``, ``UiBridge`` + headless bridges, ``LoadedExtension``,
``unload_extension_modules``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .api import (
    AGENT_EVENT_TYPES,
    LIFECYCLE_EVENT_TYPES,
    ExtensionApi,
    ExtensionContext,
    MainViewHandle,
    NullUiBridge,
    StderrUiBridge,
    ToolCallMarkup,
    UiBridge,
)
from .loader import LoadedExtension, load_extensions, unload_extension_modules
from .runtime import ExtensionRuntime, InputHookOutcome


@dataclass(frozen=True, slots=True)
class Extension:
    name: str
    path: Path
    enabled: bool = True


def discover_extensions(extensions_dir: Path | None = None) -> list[Extension]:
    from ..paths import ProverPaths

    d = extensions_dir or ProverPaths().config_dir / "extensions"
    if not d.exists():
        return []
    out: list[Extension] = []
    for p in d.glob("*.py"):
        out.append(Extension(name=p.stem, path=p))
    for init in d.glob("*/__init__.py"):
        out.append(Extension(name=init.parent.name, path=init.parent))
    return out


__all__ = [
    "AGENT_EVENT_TYPES",
    "LIFECYCLE_EVENT_TYPES",
    "Extension",
    "ExtensionApi",
    "ExtensionContext",
    "ExtensionRuntime",
    "InputHookOutcome",
    "LoadedExtension",
    "MainViewHandle",
    "NullUiBridge",
    "StderrUiBridge",
    "ToolCallMarkup",
    "UiBridge",
    "discover_extensions",
    "load_extensions",
    "unload_extension_modules",
]

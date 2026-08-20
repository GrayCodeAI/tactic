from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Extension:
    name: str
    path: Path
    enabled: bool = True


def discover_extensions(extensions_dir: Path | None = None) -> list[Extension]:
    from .paths import ProverPaths

    d = extensions_dir or ProverPaths().config_dir / "extensions"
    if not d.exists():
        return []
    return [Extension(name=p.stem, path=p) for p in d.glob("*.py")]


def load_extensions(extensions_dir: Path | None = None) -> list[Extension]:
    return discover_extensions(extensions_dir)

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Skill:
    name: str
    description: str
    content: str


def load_skills(skills_dir: Path | None = None) -> list[Skill]:
    from .paths import ProverPaths

    d = skills_dir or ProverPaths().config_dir / "skills"
    if not d.exists():
        return []
    out: list[Skill] = []
    for p in d.glob("*.md"):
        out.append(Skill(name=p.stem, description=p.stem, content=p.read_text(errors="replace")[:4000]))
    return out

"""Skill discovery and loading — Tau skills.py port, lean-adapted.

``Skill`` is a named, loaded skill file (``SKILL.md``) with optional
``disable_model_invocation`` flag.  Discovery scans the resource dirs from
``TauResourcePaths.skills_dirs``; frontmatter parsing follows the
``---``-delimited convention.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class Skill:
    name: str
    description: str
    content: str
    path: Path | None = None
    disable_model_invocation: bool = False


def load_skills(skills_dir: Path | None = None) -> list[Skill]:
    from .paths import ProverPaths

    d = skills_dir or ProverPaths().config_dir / "skills"
    if not d.exists():
        return []
    out: list[Skill] = []
    for p in sorted(d.glob("*.md")):
        skill = _parse_skill_file(p)
        if skill is not None:
            out.append(skill)
    return out


def load_skills_with_diagnostics(skills_dirs: tuple[Path, ...] = ()) -> tuple[list[Skill], list[Any]]:
    """Load skills from multiple dirs, returning (skills, diagnostics)."""
    skills: list[Skill] = []
    diagnostics: list[Any] = []
    for skills_dir in skills_dirs:
        if not skills_dir.exists():
            continue
        for p in sorted(skills_dir.glob("*.md")):
            try:
                skill = _parse_skill_file(p)
                if skill is not None:
                    skills.append(skill)
            except (OSError, UnicodeDecodeError) as exc:
                diagnostics.append({"kind": "skill_parse_error", "path": str(p), "error": str(exc)})
    return skills, diagnostics


def _parse_skill_file(path: Path) -> Skill | None:
    text = path.read_text(encoding="utf-8", errors="replace")
    name = path.stem
    description = name
    disable_model_invocation = False
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            frontmatter = text[3:end].strip()
            body = text[end + 3:].strip()
            for line in frontmatter.splitlines():
                line = line.strip()
                if line.startswith("name:"):
                    name = line.split(":", 1)[1].strip()
                elif line.startswith("description:"):
                    description = line.split(":", 1)[1].strip()
                elif line.startswith("disable_model_invocation:"):
                    val = line.split(":", 1)[1].strip().lower()
                    disable_model_invocation = val in ("true", "yes", "1")
            return Skill(
                name=name,
                description=description,
                content=body or text,
                path=path,
                disable_model_invocation=disable_model_invocation,
            )
    return Skill(name=name, description=description, content=text, path=path)


def expand_skill_command(text: str) -> str:
    """Expand a skill invocation (tau expand_skill_command)."""
    text = text.strip()
    if not text.startswith("/skill:") and not text.startswith("/skill "):
        return text
    skill_name = text.split(":", 1)[1].strip() if ":" in text else text.split(" ", 1)[1].strip()
    skill = _find_skill(skill_name)
    if skill is None:
        return f"Skill not found: {skill_name}"
    return skill.content


def parse_skill_invocation(text: str) -> tuple[str | None, str | None]:
    """Parse (skill_name, rest) from a skill invocation (tau parse_skill_invocation)."""
    stripped = text.strip()
    if not stripped.startswith("/skill:"):
        return None, None
    rest = stripped[len("/skill:"):].strip()
    parts = rest.split(" ", 1)
    return parts[0].strip(), parts[1].strip() if len(parts) > 1 else None


def _find_skill(name: str) -> Skill | None:
    for skill in load_skills():
        if skill.name == name:
            return skill
    return None
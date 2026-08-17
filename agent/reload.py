"""Reload result accounting for /reload (ports tau's CodingReloadSummary).

Captures before/after counts across the resources the TUI reloads from disk
(problems, themes, prompt templates, trust decisions) and renders a single
compact Pi-style summary line so operators can see what discovery churned.
"""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass

from .paths import TacticPaths


@dataclass(frozen=True, slots=True)
class ReloadCategorySummary:
    """before/after counts for one reloadable resource category."""

    name: str
    before: int
    after: int

    @property
    def delta(self) -> int:
        return self.after - self.before

    @property
    def changed(self) -> bool:
        return self.delta != 0


@dataclass(frozen=True, slots=True)
class ReloadSummary:
    """Aggregate reload summary line."""

    categories: tuple[ReloadCategorySummary, ...]

    @property
    def changed_any(self) -> bool:
        return any(c.changed for c in self.categories)

    def render(self) -> str:
        parts = [f"{c.name} {c.before}→{c.after}" for c in self.categories]
        if not any(c.changed for c in self.categories):
            return "· ".join(parts) + " — no changes"
        return "· ".join(parts)


@dataclass(slots=True)
class ReloadSnapshot:
    """Mutable before/after counter bag for a reload."""

    problems: int = 0
    themes: int = 0
    prompt_templates: int = 0
    trust: int = 0


def take_reload_snapshot() -> ReloadSnapshot:
    """Capture counts for the reloadable resources at one point in time."""
    from .prompt_templates import load_prompt_templates
    from .themes import available_tui_theme_names

    snap = ReloadSnapshot()
    try:
        snap.prompt_templates = len(load_prompt_templates())
    except OSError:
        snap.prompt_templates = 0
    try:
        snap.themes = len(available_tui_theme_names())
    except OSError:
        snap.themes = 0
    with suppress(Exception):
        store_dir = TacticPaths().config_dir
        snap.trust = sum(
            1 for _ in (store_dir.glob("trust*") if store_dir.exists() else [])
        )
    return snap


def build_reload_summary(before: ReloadSnapshot, after: ReloadSnapshot) -> ReloadSummary:
    return ReloadSummary((
        ReloadCategorySummary("problems", before.problems, after.problems),
        ReloadCategorySummary("themes", before.themes, after.themes),
        ReloadCategorySummary("prompts", before.prompt_templates, after.prompt_templates),
        ReloadCategorySummary("trust", before.trust, after.trust),
    ))
"""reload.py summary accounting tests (tau CodingReloadSummary parity)."""

from __future__ import annotations

from agent.reload import (
    ReloadCategorySummary,
    ReloadSnapshot,
    build_reload_summary,
)


def test_category_summary_delta_and_changed() -> None:
    c = ReloadCategorySummary("problems", 10, 13)
    assert c.delta == 3
    assert c.changed is True
    assert ReloadCategorySummary("themes", 2, 2).changed is False


def test_summary_render_with_and_without_changes() -> None:
    before = ReloadSnapshot(problems=10, themes=2, prompt_templates=4, trust=1)
    after = ReloadSnapshot(problems=13, themes=2, prompt_templates=4, trust=1)
    s = build_reload_summary(before, after)
    out = s.render()
    assert "problems 10→13" in out
    assert "themes 2→2" in out
    assert " changed" not in out  # delta 0
    assert "no changes" in build_reload_summary(before, before).render()


def test_summary_changed_any_flags() -> None:
    before = ReloadSnapshot(problems=10)
    after = ReloadSnapshot(problems=12)
    assert build_reload_summary(before, after).changed_any is True
    assert build_reload_summary(before, before).changed_any is False


def test_snapshot_defaults_are_zero() -> None:
    snap = ReloadSnapshot()
    assert snap == ReloadSnapshot(problems=0, themes=0, prompt_templates=0, trust=0)

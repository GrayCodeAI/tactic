"""Resizable-pane tests — PaneDivider drag, double-click reset, persistence."""

from __future__ import annotations

import pytest
from textual import events
from textual.containers import Vertical

from agent.tui import (
    PaneDivider,
    ProverApp,
    TuiSettings,
    load_tui_settings,
    save_tui_settings,
)


def _divider_x_y(pilot) -> tuple[int, int, int]:
    """Screen coords inside the divider and its current width."""
    div = pilot.app.query_one(PaneDivider)
    x, y = div.region.x + 1, div.region.y + 5
    width = pilot.app.query_one("#problems", Vertical).styles.width
    return x, y, int(getattr(width, "value", width))


@pytest.mark.anyio
async def test_divider_between_panes() -> None:
    app = ProverApp()
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        div = app.query_one(PaneDivider)
        assert div.ALLOW_SELECT is False
        # divider sits between the problems pane and the side panes
        problems = app.query_one("#problems", Vertical)
        assert div.region.x > problems.region.x
        assert div.styles.width.value == 2
        assert app.query_one("#problems", Vertical).styles.width.value == 46


@pytest.mark.anyio
async def test_drag_resizes_problems_pane(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROVER_CONFIG_DIR", str(tmp_path / "config"))
    app = ProverApp()
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        await pilot.mouse_down(PaneDivider, offset=(1, 5), button=0)
        await pilot.pause()
        div = app.query_one(PaneDivider)
        assert div._dragging

        x0, y0, start_width = _divider_x_y(pilot)
        app.post_message(events.MouseMove(
            None, x=x0 + 20, y=y0, delta_x=20, delta_y=0,
            button=0, shift=False, meta=False, ctrl=False,
            screen_x=x0 + 20, screen_y=y0,
        ))
        await pilot.pause()
        width = app.query_one("#problems", Vertical).styles.width
        assert int(width.value) == start_width + 20
        assert app.tui_settings.problem_pane_width == start_width + 20

        await pilot.mouse_up(PaneDivider, offset=(1, 5))
        await pilot.pause()
        assert not div._dragging
        # release persists to ~/.prover/tui.json
        assert load_tui_settings().problem_pane_width == start_width + 20


@pytest.mark.anyio
async def test_drag_clamps_within_bounds(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROVER_CONFIG_DIR", str(tmp_path / "config"))
    app = ProverApp()
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        x0, y0, _start_width = _divider_x_y(pilot)
        await pilot.mouse_down(PaneDivider, offset=(1, 5), button=0)
        await pilot.pause()
        # drag far past every limit
        app.post_message(events.MouseMove(
            None, x=x0 + 9999, y=y0, delta_x=9999, delta_y=0,
            button=0, shift=False, meta=False, ctrl=False,
            screen_x=x0 + 9999, screen_y=y0,
        ))
        await pilot.pause()
        width = app.query_one("#problems", Vertical).styles.width
        # terminal is 140 wide, min side width 40 → max pane = 100
        assert int(width.value) == 100
        app.post_message(events.MouseMove(
            None, x=x0 - 9999, y=y0, delta_x=-9999, delta_y=0,
            button=0, shift=False, meta=False, ctrl=False,
            screen_x=x0 - 9999, screen_y=y0,
        ))
        await pilot.pause()
        width = app.query_one("#problems", Vertical).styles.width
        assert int(width.value) == PaneDivider.MIN_WIDTH
        await pilot.mouse_up(PaneDivider, offset=(1, 5))
        await pilot.pause()


@pytest.mark.anyio
async def test_double_click_resets_width(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROVER_CONFIG_DIR", str(tmp_path / "config"))
    app = ProverApp()
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        save_tui_settings(TuiSettings(problem_pane_width=120))
        app.tui_settings = TuiSettings(problem_pane_width=120)
        div = app.query_one(PaneDivider)
        div.post_message(events.Click(
            div, x=1, y=5, delta_x=0, delta_y=0, button=0,
            shift=False, meta=False, ctrl=False, chain=2,
        ))
        await pilot.pause()
        width = app.query_one("#problems", Vertical).styles.width
        assert int(width.value) == PaneDivider.DEFAULT_WIDTH
        assert app.tui_settings.problem_pane_width == PaneDivider.DEFAULT_WIDTH
        assert load_tui_settings().problem_pane_width == PaneDivider.DEFAULT_WIDTH


@pytest.mark.anyio
async def test_persisted_width_applied_on_mount(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROVER_CONFIG_DIR", str(tmp_path / "config"))
    save_tui_settings(TuiSettings(problem_pane_width=80))
    app = ProverApp()
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        width = app.query_one("#problems", Vertical).styles.width
        assert int(width.value) == 80
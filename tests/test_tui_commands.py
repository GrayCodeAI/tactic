"""Slash-command TUI integration tests — the frontend half of tau's
test_commands.py (which only exercises the pure parser).

Drives the real app headlessly: prompt bar submission, command result
dispatch, message modals, and Tab-equivalent (ctrl+space) completion.
"""

from __future__ import annotations

import pytest
from textual.widgets import Input

from agent.tui import MessageScreen, ProverApp, ProveScreen, SelectableRichLog


async def submit(pilot, text: str) -> None:
    """Type into the prompt bar and press Enter (tau's _submit equivalent)."""
    prompt = pilot.app.query_one("#prompt", Input)
    prompt.focus()
    prompt.value = text
    await pilot.pause()
    res = pilot.press("enter")
    if hasattr(res, "__await__"):
        await res
    await pilot.pause()


@pytest.mark.anyio
async def test_status_command_shows_modal() -> None:
    app = ProverApp()
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        await submit(pilot, "/status")
        assert isinstance(app.screen, MessageScreen)
        assert "Qwen" in app.screen._body or "idle" in app.screen._body
        await pilot.press("q")
        await pilot.pause()


@pytest.mark.anyio
async def test_workers_command_sets_parallelism() -> None:
    app = ProverApp()
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        await submit(pilot, "/workers 4")
        assert app.n_workers == 4


@pytest.mark.anyio
async def test_help_command_lists_commands() -> None:
    app = ProverApp()
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        await submit(pilot, "/help")
        assert isinstance(app.screen, MessageScreen)
        assert "/prove" in app.screen._body
        assert "/quit" in app.screen._body
        await pilot.press("q")
        await pilot.pause()


@pytest.mark.anyio
async def test_clear_command_empties_log() -> None:
    from textual.selection import SELECT_ALL

    app = ProverApp()
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        await submit(pilot, "/clear")
        selected = app.query_one("#log", SelectableRichLog).get_selection(SELECT_ALL)
        assert selected is None or selected[0].strip() == ""


@pytest.mark.anyio
async def test_completions_appear_and_ctrl_space_completes() -> None:
    app = ProverApp()
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        prompt = app.query_one("#prompt", Input)
        prompt.focus()
        prompt.value = "/prov"
        await pilot.pause()
        assert app.query_one("#prompt-completions").styles.display == "block"

        res = pilot.press("ctrl+space")
        if hasattr(res, "__await__"):
            await res
        await pilot.pause()
        assert prompt.value.startswith("/prove")


@pytest.mark.anyio
async def test_prove_command_opens_editor_modal() -> None:
    app = ProverApp()
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        await submit(pilot, "/prove")
        assert isinstance(app.screen, ProveScreen)
        await pilot.press("escape")
        await pilot.pause()


@pytest.mark.anyio
async def test_unknown_command_does_not_crash() -> None:
    app = ProverApp()
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        await submit(pilot, "/bads")  # unknown command — must not raise

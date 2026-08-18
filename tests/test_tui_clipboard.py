"""Clipboard / selection tests for the TUI — ported from huggingface/tau
(tests/test_tui_app.py). Tau's TUI:

- overrides App.copy_to_clipboard to try pyperclip first, then Textual's
  OSC 52 fallback;
- auto-copies selected text on TextSelected when the
  TuiSettings.auto_copy_selection flag (or a screen-level
  auto_copy_selection attribute) is on;
- disables native selection while the agent is running so a mutating
  transcript does not move the selection out from under the user.

Prover equivalents: ProveScreen/main panels ~ transcript messages,
ReplayScreen ~ tau's session modal (its content is always the copy
target), LeaderboardScreen ~ tau's non-session command modal.
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest
from textual.app import App
from textual.geometry import Offset
from textual.selection import SELECT_ALL, Selection

from agent.tui import (
    LeaderboardScreen,
    ProverApp,
    ReplayScreen,
    SelectableRichLog,
    TuiSettings,
)


def _write_session(path: Path, problem_id: str = "sq_nonneg") -> Path:
    """Write a minimal JSONL session file and return its path."""
    recs = [
        {"t": 1, "event": "start", "problem_id": problem_id,
         "statement": "theorem sq_nonneg (x : ℤ) : 0 ≤ x ^ 2 := by sorry",
         "max_steps": 20, "model": "test-model"},
        {"t": 2, "event": "hammer", "i": 1, "total": 10, "tactic": "ring",
         "ok": True, "output": ""},
        {"t": 3, "event": "result", "proved": True, "steps": 1, "seconds": 3.2,
         "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
         "cost_usd": 0.0, "stopped": False, "session_id": path.stem},
    ]
    path.write_text("\n".join(json.dumps(r) for r in recs) + "\n")
    return path


@pytest.mark.anyio
async def test_tui_selectable_rich_log_extracts_plain_text_selection(tmp_path) -> None:
    """SelectableRichLog exposes the plain-text of every write to Selection
    extraction (tau's TranscriptMessageWidget.get_selection behavior)."""
    app = ProverApp()
    async with app.run_test(size=(120, 30)) as pilot:
        log = app.query_one("#log", SelectableRichLog)
        log.clear()
        log.write("copy this")
        log.write("second line")
        await pilot.pause()

        assert log.get_selection(SELECT_ALL) == ("copy this\nsecond line", "\n")
        assert log.get_selection(Selection(Offset(5, 0), Offset(9, 0))) == ("this", "\n")
        assert log.get_selection(Selection(Offset(0, 1), Offset(6, 1))) == ("second", "\n")
        # open-ended start: from col 6 of first line to end of document
        # ("copy this"[6:] == "his", plus the rest)
        assert log.get_selection(Selection(Offset(6, 0), None)) == ("his\nsecond line", "\n")

        log.clear()
        assert log.get_selection(SELECT_ALL) is None


@pytest.mark.anyio
async def test_tui_auto_copies_selected_text_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = ProverApp(tui_settings=TuiSettings(auto_copy_selection=True))
    copied: list[str] = []
    monkeypatch.setattr(app, "copy_to_clipboard", copied.append)

    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        log = app.query_one("#log", SelectableRichLog)
        log.clear()
        log.write("copy this")
        await pilot.pause()
        app.screen.selections = {log: SELECT_ALL}

        await app.on_text_selected()

    assert copied == ["copy this"]


@pytest.mark.anyio
async def test_tui_auto_copy_selection_can_be_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = ProverApp(tui_settings=TuiSettings(auto_copy_selection=False))
    copied: list[str] = []
    monkeypatch.setattr(app, "copy_to_clipboard", copied.append)

    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        log = app.query_one("#log", SelectableRichLog)
        log.clear()
        log.write("do not copy")
        await pilot.pause()
        app.screen.selections = {log: SELECT_ALL}

        await app.on_text_selected()

    assert copied == []


@pytest.mark.anyio
async def test_replay_screen_auto_copies_selected_text(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """tau: the session modal always copies selections, even when the global
    auto_copy_selection setting is off."""
    session_path = _write_session(tmp_path / "20260101-000000-sq_nonneg.jsonl")
    app = ProverApp(tui_settings=TuiSettings(auto_copy_selection=False))
    copied: list[str] = []
    monkeypatch.setattr(app, "copy_to_clipboard", copied.append)

    async with app.run_test(size=(120, 30)) as pilot:
        app.push_screen(ReplayScreen(session_path))
        await pilot.pause()

        assert isinstance(app.screen, ReplayScreen)
        body = app.screen.query_one("#rlog", SelectableRichLog)
        app.screen.selections = {body: SELECT_ALL}

        await app.on_text_selected()

    assert copied
    assert "PROVED" in copied[0]
    assert "hammer 1/10: `ring`" in copied[0]


@pytest.mark.anyio
async def test_non_session_modal_uses_global_auto_copy_setting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """tau: command modals that are not the session modal follow the global
    setting — here the leaderboard modal copies nothing when it is off."""
    app = ProverApp(tui_settings=TuiSettings(auto_copy_selection=False))
    copied: list[str] = []
    monkeypatch.setattr(app, "copy_to_clipboard", copied.append)

    async with app.run_test(size=(120, 30)) as pilot:
        app.push_screen(LeaderboardScreen())
        await pilot.pause()

        assert isinstance(app.screen, LeaderboardScreen)
        table = app.screen.query_one("#board-table")
        app.screen.selections = {table: SELECT_ALL}

        await app.on_text_selected()

    assert copied == []


@pytest.mark.anyio
async def test_tui_app_disables_text_selection_while_agent_is_running() -> None:
    app = ProverApp()

    async with app.run_test(size=(120, 30)):
        assert app.ALLOW_SELECT is True

        app._run_active = True
        app._sync_text_selection_state()

        assert app.ALLOW_SELECT is False

        app._run_active = False
        app._sync_text_selection_state()

        assert app.ALLOW_SELECT is True


@pytest.mark.anyio
async def test_copy_to_clipboard_prefers_pyperclip(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """tau: copy_to_clipboard goes through pyperclip when it is importable,
    and still calls Textual's fallback afterward."""
    fake = types.ModuleType("pyperclip")
    copied: list[str] = []
    fake.copy = copied.append  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pyperclip", fake)
    textual_copied: list[str] = []
    monkeypatch.setattr(
        App, "copy_to_clipboard", lambda self, text: textual_copied.append(text)
    )

    app = ProverApp()
    async with app.run_test(size=(120, 30)):
        app.copy_to_clipboard("hello")

    assert copied == ["hello"]
    assert textual_copied == ["hello"]


@pytest.mark.anyio
async def test_copy_to_clipboard_falls_back_without_pyperclip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """tau: without pyperclip the copy silently uses Textual's built-in path."""
    monkeypatch.setitem(sys.modules, "pyperclip", None)  # make import fail
    textual_copied: list[str] = []
    monkeypatch.setattr(
        App, "copy_to_clipboard", lambda self, text: textual_copied.append(text)
    )

    app = ProverApp()
    async with app.run_test(size=(120, 30)):
        app.copy_to_clipboard("fallback text")

    assert textual_copied == ["fallback text"]

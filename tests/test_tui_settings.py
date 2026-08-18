"""TUI settings persistence tests (tau tui/config.py save/load parity)."""

from __future__ import annotations

import json

import pytest

from agent.tui import (
    TuiSettings,
    load_tui_settings,
    save_tui_settings,
    tui_settings_path,
)


def test_settings_path_follows_config_dir(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TACTIC_CONFIG_DIR", str(tmp_path / "config"))
    assert tui_settings_path() == tmp_path / "config" / "tui.json"


def test_save_then_load_round_trips(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TACTIC_CONFIG_DIR", str(tmp_path / "config"))
    settings = TuiSettings(
        auto_copy_selection=True, theme="tactic-light",
        notification="bell", thinking_level="high",
    )
    save_tui_settings(settings)
    assert load_tui_settings() == settings


def test_load_returns_defaults_when_missing(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TACTIC_CONFIG_DIR", str(tmp_path / "absent"))
    assert load_tui_settings() == TuiSettings()


def test_load_survives_invalid_json(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TACTIC_CONFIG_DIR", str(tmp_path / "config"))
    path = tui_settings_path()
    path.parent.mkdir(parents=True)
    path.write_text("{not json", encoding="utf-8")
    assert load_tui_settings() == TuiSettings()


def test_load_clamps_invalid_values(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TACTIC_CONFIG_DIR", str(tmp_path / "config"))
    path = tui_settings_path()
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        "auto_copy_selection": True, "theme": "tactic-dark",
        "notification": "weird", "thinking_level": "bogus",
    }), encoding="utf-8")
    loaded = load_tui_settings()
    assert loaded.notification == "auto"        # invalid → default
    assert loaded.thinking_level == ""          # invalid → cleared
    assert loaded.auto_copy_selection is True


def test_from_json_ignores_unknown_keys(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TACTIC_CONFIG_DIR", str(tmp_path / "config"))
    path = tui_settings_path()
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"theme": "high-contrast", "future_key": 1}),
                    encoding="utf-8")
    loaded = load_tui_settings()
    assert loaded.theme == "high-contrast"
    assert loaded.notification == TuiSettings.notification


@pytest.fixture(autouse=True)
def _clear_thinking_override():
    """Keep thinking.set_thinking_level() from leaking across tests."""
    from agent import thinking

    yield
    thinking.clear_thinking_level()

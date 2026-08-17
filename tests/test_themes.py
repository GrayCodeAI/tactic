"""Theme + terminal title tests — ported from huggingface/tau
tests/test_tui_themes.py and the terminal-title contract.
"""

from __future__ import annotations

import pytest

from agent import terminal_title as tt
from agent import themes
from agent.tui import TacticApp, TuiSettings


def _theme_json(name: str, **color_overrides: str) -> dict:
    colors = {
        "screen_background": "#12141c", "screen_text": "#e6e8ee",
        "chrome_background": "#1b1e2a", "chrome_text": "#a9b0c0",
        "muted_text": "#6f7689", "sidebar_background": "#161925",
        "border": "#2d3142", "prompt_background": "#1b1e2a",
        "prompt_text": "#e6e8ee", "prompt_border": "#3f6cff",
        "accent": "#3f6cff", "success": "#34d178", "error": "#ff5f87",
        "warn": "#ffbb44",
    }
    colors.update(color_overrides)
    return {"name": name, "dark": True, "colors": colors}


def test_builtin_themes_present() -> None:
    names = themes.available_tui_theme_names()
    assert "tactic-dark" in names
    assert "tactic-light" in names
    assert "high-contrast" in names
    assert themes.get_tui_theme("tactic-dark").dark is True
    assert themes.get_tui_theme("tactic-light").dark is False


def test_high_contrast_bright_accent() -> None:
    assert themes.get_tui_theme("high-contrast").prompt_border == "#00ff66"


def test_unknown_theme_raises() -> None:
    import pytest

    with pytest.raises(KeyError):
        themes.get_tui_theme("does-not-exist")


def test_parse_theme_rejects_missing_colors() -> None:
    import pytest

    record = _theme_json("broken")
    del record["colors"]["accent"]
    with pytest.raises(ValueError):
        themes._parse_theme(record)


def test_parse_theme_rejects_bad_colors_type() -> None:
    import pytest

    record = _theme_json("bad")
    record["colors"] = "not a dict"
    with pytest.raises(TypeError):
        themes._parse_theme(record)


def test_css_variables_map_all_roles() -> None:
    theme = themes.get_tui_theme("tactic-dark")
    css = themes.theme_css_variables(theme)
    assert css["tactic-accent"] == theme.accent
    assert css["tactic-screen-background"] == theme.screen_background
    assert css["tactic-prompt-border"] == theme.prompt_border


def test_textual_theme_variables_use_accent_as_primary() -> None:
    theme = themes.get_tui_theme("tactic-dark")
    css = themes.textual_theme_variables(theme)
    assert css["primary"] == theme.accent
    assert css["background"] == theme.screen_background


@pytest.mark.anyio
async def test_tui_applies_theme_and_registers_themes() -> None:
    app = TacticApp(tui_settings=TuiSettings(theme="tactic-light"))
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        assert app.theme == "tactic-light" or app.theme in themes.available_tui_theme_names()
        assert app.resolved_theme.name == "tactic-light"
        assert app.dark is False


@pytest.mark.anyio
async def test_tui_falls_back_to_dark_on_unknown_theme() -> None:
    app = TacticApp(tui_settings=TuiSettings(theme="nope"))
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        assert app.resolved_theme.name == "tactic-dark"


# ---------------------------------------------------------------- terminal title


def test_terminal_title_mark_when_idle() -> None:
    assert tt.build_terminal_title(None) == tt.TAU_TITLE_MARK
    assert tt.build_terminal_title("") == tt.TAU_TITLE_MARK
    assert tt.build_terminal_title("sq_nonneg") == "τ | sq_nonneg"


def test_terminal_title_braille_frame_when_running() -> None:
    t0 = tt.build_terminal_title("run", running=True, frame=0)
    t9 = tt.build_terminal_title("run", running=True, frame=9)
    assert t0.startswith(tt.RUNNING_TITLE_FRAMES[0])
    assert t9.startswith(tt.RUNNING_TITLE_FRAMES[9])
    assert t0 != t9


def test_terminal_title_cycles_frames() -> None:
    t0 = tt.build_terminal_title("x", running=True, frame=0)
    t10 = tt.build_terminal_title("x", running=True, frame=10)
    assert t0 == t10  # wraps modulo frame count


def test_sanitize_title_strips_control_chars_and_caps_length() -> None:
    dirty = "a\x01b\x7fc"
    assert tt.sanitize_terminal_title(dirty) == "abc"
    long = "x" * 200
    capped = tt.sanitize_terminal_title(long)
    assert len(capped) <= tt.MAX_TERMINAL_TITLE_LENGTH
    assert capped.endswith("…")


def test_osc_sequence_format() -> None:
    seq = tt.osc_terminal_title_sequence("title")
    assert seq == "\x1b]0;title\x07"

"""TUI themes (ported from huggingface/tau tui/themes — themes are data, not code).

Built-in themes ship as parsed JSON records; custom themes can be dropped
in ~/.tactic/themes/*.json with the same shape. A theme is registered with
Textual as a real Theme plus a CSS-variable map, so every screen that uses
$theme variables picks the palette up automatically.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class TuiTheme:
    """Color palette for the tactic TUI (subset of tau's TuiTheme)."""

    name: str
    dark: bool
    screen_background: str
    screen_text: str
    chrome_background: str
    chrome_text: str
    muted_text: str
    sidebar_background: str
    border: str
    prompt_background: str
    prompt_text: str
    prompt_border: str
    accent: str
    success: str
    error: str
    warn: str


_TACTIC_DARK_JSON = """{
  "name": "tactic-dark",
  "dark": true,
  "colors": {
    "screen_background": "#12141c",
    "screen_text": "#e6e8ee",
    "chrome_background": "#1b1e2a",
    "chrome_text": "#a9b0c0",
    "muted_text": "#6f7689",
    "sidebar_background": "#161925",
    "border": "#2d3142",
    "prompt_background": "#1b1e2a",
    "prompt_text": "#e6e8ee",
    "prompt_border": "#3f6cff",
    "accent": "#3f6cff",
    "success": "#34d178",
    "error": "#ff5f87",
    "warn": "#ffbb44"
  }
}"""

_TACTIC_LIGHT_JSON = """{
  "name": "tactic-light",
  "dark": false,
  "colors": {
    "screen_background": "#fdfdfd",
    "screen_text": "#1a1d29",
    "chrome_background": "#eef0f6",
    "chrome_text": "#535a6e",
    "muted_text": "#8b91a3",
    "sidebar_background": "#f4f5fa",
    "border": "#cfd3e0",
    "prompt_background": "#eef0f6",
    "prompt_text": "#1a1d29",
    "prompt_border": "#2c5ce6",
    "accent": "#2c5ce6",
    "success": "#0e9a55",
    "error": "#d6294f",
    "warn": "#c47b00"
  }
}"""

_HIGH_CONTRAST_JSON = """{
  "name": "high-contrast",
  "dark": true,
  "colors": {
    "screen_background": "#000000",
    "screen_text": "#ffffff",
    "chrome_background": "#101010",
    "chrome_text": "#ffffff",
    "muted_text": "#b0b0b0",
    "sidebar_background": "#080808",
    "border": "#ffffff",
    "prompt_background": "#101010",
    "prompt_text": "#ffffff",
    "prompt_border": "#00ff66",
    "accent": "#00ff66",
    "success": "#00ff66",
    "error": "#ff3333",
    "warn": "#ffff00"
  }
}"""

BUILTIN_TUI_THEMES: dict[str, TuiTheme] = {}
_custom_themes: dict[str, TuiTheme] = {}


def _parse_theme(record: dict) -> TuiTheme:
    name = record.get("name")
    if not isinstance(name, str) or not name:
        raise ValueError("theme JSON requires a string 'name'")
    colors = record.get("colors")
    if not isinstance(colors, dict):
        raise TypeError(f"theme {name!r}: 'colors' must be a JSON object")
    fields = TuiTheme.__dataclass_fields__
    missing = [f for f in fields if f not in ("name", "dark") and f not in colors]
    if missing:
        raise ValueError(f"theme {name!r}: missing colors: {', '.join(missing)}")
    dark = record.get("dark", "dark" in name)
    return TuiTheme(name=name, dark=bool(dark),
                    **{f: str(colors[f]) for f in fields if f not in ("name", "dark")})


def _load_builtin_themes() -> None:
    if BUILTIN_TUI_THEMES:
        return
    for raw in (_TACTIC_DARK_JSON, _TACTIC_LIGHT_JSON, _HIGH_CONTRAST_JSON):
        theme = _parse_theme(json.loads(raw))
        BUILTIN_TUI_THEMES[theme.name] = theme


_load_builtin_themes()

TAU_DARK_THEME = BUILTIN_TUI_THEMES["tactic-dark"]  # default, tau naming parity


def themes_dir() -> Path:
    from .paths import TacticPaths

    return TacticPaths().themes_dir


def load_custom_themes() -> None:
    """Load user themes from ~/.tactic/themes/*.json (tau parity)."""
    _custom_themes.clear()
    d = themes_dir()
    if not d.exists():
        return
    for p in sorted(d.glob("*.json")):
        try:
            theme = _parse_theme(json.loads(p.read_text(encoding="utf-8")))
        except (ValueError, TypeError, json.JSONDecodeError, OSError):
            continue
        if theme.name in BUILTIN_TUI_THEMES:
            continue
        _custom_themes[theme.name] = theme


def available_tui_theme_names() -> tuple[str, ...]:
    """Built-ins first, then custom themes sorted (tau ordering)."""
    return (*BUILTIN_TUI_THEMES, *sorted(_custom_themes))


def get_tui_theme(name: str) -> TuiTheme:
    if not _custom_themes:
        load_custom_themes()
    theme = BUILTIN_TUI_THEMES.get(name) or _custom_themes.get(name)
    if theme is None:
        raise KeyError(f"unknown theme: {name}")
    return theme


def theme_css_variables(theme: TuiTheme) -> dict[str, str]:
    """CSS variables exposed to the app's CSS (tau's theme_css_variables)."""
    return {
        "tactic-screen-background": theme.screen_background,
        "tactic-chrome-background": theme.chrome_background,
        "tactic-sidebar-background": theme.sidebar_background,
        "tactic-border": theme.border,
        "tactic-muted": theme.muted_text,
        "tactic-accent": theme.accent,
        "tactic-warn": theme.warn,
        "tactic-prompt-border": theme.prompt_border,
    }


def textual_theme_variables(theme: TuiTheme) -> dict[str, str]:
    """Textual Theme color overrides (tau's mapping: primary=accent, etc.)."""
    return {
        "primary": theme.accent,
        "secondary": theme.border,
        "background": theme.screen_background,
        "surface": theme.chrome_background,
        "panel": theme.chrome_background,
        "foreground": theme.screen_text,
        "error": theme.error,
        "warning": theme.warn,
        "success": theme.success,
    }

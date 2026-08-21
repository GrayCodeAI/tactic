"""Layered user settings — adapted from fx's settings/config-precedence model.

fx resolves configuration through a single documented precedence chain:
environment > user settings (workspace > global) > project defaults > built-in.

lean-prover adopts the same idea as one small, typed loader: every user-facing
knob is read from ``~/.prover/settings.json`` with a single precedence rule
(highest wins), so there is one place to look and one rule to remember.

Precedence (highest wins):

1. Environment variable (``PROVER_<KEY>``), when set
2. ``<workspace>/.prover/settings.json`` (project settings) — optional
3. ``~/.prover/settings.json`` (user/global settings)
4. Built-in default for the key

Keys are the lower-cased, underscore form of each setting name (see
:py:data:`DEFAULTS`). Environment overrides use the ``PROVER_`` prefix and
uppercase the key, e.g. setting ``max_steps`` -> ``PROVER_MAX_STEPS``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .paths import ProverPaths

# name -> (default, json_type, doc). json_type is the expected JSON value type
# used to reject wrong-typed values in a config file.
DEFAULTS: dict[str, tuple[Any, str, str]] = {
    "max_steps": (20, "int", "default max repair steps for a proof"),
    "context_window": (0, "int", "0 = auto; token budget for history compaction"),
    "workers": (1, "int", "default parallel proof workers"),
    "theme": ("prover-dark", "str", "TUI theme name"),
    "thinking": ("off", "str", "default thinking level"),
    "permission_mode": ("ask", "str", "ask|auto|yolo baseline for tool approval"),
    "quiet": (False, "bool", "suppress non-essential output (best for scripts)"),
}


def canonical_key(name: str) -> str:
    """Normalise a setting name to its canonical (lower, underscore) form."""
    return name.strip().lower().replace("-", "_")


def env_name(key: str) -> str:
    """Return the env var that overrides ``key`` (``PROVER_<KEY>``)."""
    return "PROVER_" + key.upper()


def _coerce(key: str, raw: Any) -> Any:
    _, json_type, _ = DEFAULTS[key]
    if json_type == "int":
        if isinstance(raw, bool) or not isinstance(raw, int):
            raise ValueError(f"setting {key}: expected an int, got {raw!r}")
        return raw
    if json_type == "bool":
        if not isinstance(raw, bool):
            raise ValueError(f"setting {key}: expected a bool, got {raw!r}")
        return raw
    # str
    if not isinstance(raw, str):
        raise TypeError(f"setting {key}: expected a string, got {raw!r}")
    return raw


def _load_layers(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """Load the user and project settings files; later files shadow earlier ones.

    Return value maps layer name -> parsed JSON dict (malformed/missing files
    are ignored so a bad settings file never breaks the agent).
    """
    paths = _resolve_files(path)
    layers: dict[str, dict[str, Any]] = {}
    for name, p in paths:
        if p is None or not p.exists():
            continue
        try:
            data = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, dict):
            continue
        layers[name] = data
    return layers


def _resolve_files(path: Path | None) -> list[tuple[str, Path | None]]:
    """Return [(layer_name, path_or_None), ...] in low->high precedence order."""
    pp = ProverPaths()
    user = path if path is not None else pp.config_dir / "settings.json"
    project = Path.cwd() / ".prover" / "settings.json"
    # project layer is higher precedence than user layer
    return [("user", user), ("project", project)]


def get(key: str, *, path: Path | None = None) -> Any:
    """Resolve a single setting through the precedence chain."""
    ckey = canonical_key(key)
    if ckey not in DEFAULTS:
        raise KeyError(f"unknown setting: {key}")
    default, json_type, _ = DEFAULTS[ckey]

    env = os.environ.get(env_name(ckey))
    if env is not None:
        return _from_env(ckey, json_type, env)

    for layer in ("project", "user"):
        data = _layers(path).get(layer, {})
        if ckey in data:
            return _coerce(ckey, data[ckey])

    return default


def all_settings(*, path: Path | None = None) -> dict[str, Any]:
    """Return every known setting resolved to its effective value."""
    return {key: get(key, path=path) for key in DEFAULTS}


def _layers(path: Path | None = None) -> dict[str, dict[str, Any]]:
    # small cache keyed by the resolved user path so repeated reads are cheap
    # but still honour a fresh path in tests.
    key = ""
    if path is not None:
        key = str(path)
    cache = getattr(_layers, "_cache", None)  # type: ignore[attr-defined]
    if cache is None:
        cache = {}
        _layers._cache = cache  # type: ignore[attr-defined]
    if key not in cache:
        cache[key] = _load_layers(path)
    return cache[key]


def _from_env(key: str, json_type: str, env: str) -> Any:
    if json_type == "int":
        try:
            return int(env)
        except ValueError:
            default, _, _ = DEFAULTS[key]
            return default
    if json_type == "bool":
        return env.strip().lower() in ("1", "true", "yes", "on")
    return env


def clear_settings_cache() -> None:
    """Drop the in-process settings cache (used by tests)."""
    _layers._cache = {}

"""Committed project defaults — adapted from fx's repo-safe project config.

fx lets a repository commit ``.fx.json`` with *only* repo-safe defaults
(sandbox, max_agent_steps, max_tool_result_bytes, context). Profile-owned keys
(model, permission, credential, ...) are rejected before parsing so a committed
file can never leak a model name, an API key, or weaken permissions.

lean-prover adopts the same shape: ``<repo>/.prover.json`` may carry only the
keys in the whitelist below. Anything else is dropped with a warning, so a
committed file can pin sane defaults without ever carrying secrets or
permission overrides.

Allowed keys (repo-safe)::

    max_steps        default max repair steps
    context_window   token budget for compaction (0 = auto)
    workers          default parallel proof workers
    quiet            suppress non-essential output in scripts
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# Whitelist of keys a committed project file may set. Guard the boundaries a
# malicious or sloppy commit should never touch: model selection, permissions,
# and credentials are *never* read from a repo file.
ALLOWED_KEYS: dict[str, type] = {
    "max_steps": int,
    "context_window": int,
    "workers": int,
    "quiet": bool,
}

# Keys a repo file is *forbidden* to set, even if a dumped profile includes them.
FORBIDDEN_KEYS: tuple[str, ...] = (
    "model",
    "permission_mode",
    "permission",
    "api_key",
    "base_url",
    "credentials",
    "provider",
)


def _find_project_file(cwd: Path | None = None) -> Path | None:
    root = Path(cwd) if cwd is not None else Path.cwd()
    candidate = root / ".prover.json"
    return candidate if candidate.exists() else None


def parse_project_defaults(
    data: Any, *, path: str | Path | None = None
) -> tuple[dict[str, Any], list[str]]:
    """Validate a parsed project config against the whitelist.

    Returns ``(allowed, warnings)``. Forbidden keys are dropped with a warning;
    unknown keys are dropped with a warning; wrong-typed values are dropped.
    """
    allowed: dict[str, Any] = {}
    warnings: list[str] = []
    source = str(path) if path is not None else "<repo>/.prover.json"

    if not isinstance(data, dict):
        warnings.append(f"{source}: project defaults must be a JSON object; ignored")
        return {}, warnings

    for key, value in data.items():
        if key in FORBIDDEN_KEYS:
            warnings.append(f"{source}: refusing repo-set {key!r} (never commit secrets/permissions); ignored")
            continue
        expected = ALLOWED_KEYS.get(key)
        if expected is None:
            warnings.append(f"{source}: unknown key {key!r}; ignored")
            continue
        if expected is bool:
            if not isinstance(value, bool):
                warnings.append(f"{source}: {key!r} must be a bool; ignored")
                continue
        elif not isinstance(value, expected):
            warnings.append(f"{source}: {key!r} must be {expected.__name__}; ignored")
            continue
        allowed[key] = value

    return allowed, warnings


def load_project_defaults(
    cwd: Path | None = None, *, env_path: str | None = None
) -> tuple[dict[str, Any], list[str]]:
    """Read and validate ``.prover.json``.

    The file to read is ``<env PROVER_PROJECT_CONFIG>`` if set, else
    ``<cwd>/.prover.json``. Missing files yield empty defaults.
    """
    path: Path | None
    if env_path:
        path = Path(env_path)
    else:
        env = os.environ.get("PROVER_PROJECT_CONFIG")
        if env:
            path = Path(env)
        else:
            path = _find_project_file(cwd)
    if path is None or not path.exists():
        return {}, []
    try:
        raw = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        return {}, [f"{path}: could not read project defaults ({exc}); ignored"]
    return parse_project_defaults(raw, path=path)


def effective_defaults(cwd: Path | None = None) -> dict[str, Any]:
    """Merge repo-safe project defaults over built-in ``settings.DEFAULTS``.

    Built-in defaults are the floor; a committed repo file only narrows/raises
    them for repo-safe keys. ``PROVER_<KEY>`` env vars always win anyway (see
    ``agent.settings``), so repo files can never override an explicit env.
    """
    from . import settings

    merged: dict[str, Any] = {}
    for key, (default, _, _) in settings.DEFAULTS.items():
        merged[key] = default
    allowed, _warnings = load_project_defaults(cwd)
    merged.update(allowed)
    return merged

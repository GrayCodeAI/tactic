"""Package version — Tau version.py port (Tau 37a9e43 src/tau_coding/version.py).

Reads the version from pyproject.toml so a single source of truth stays put.
Falls back to a static string when the file is unreadable (e.g. installed
wheel with loader quirks).
"""

from __future__ import annotations

import re
from pathlib import Path

_FALLBACK_VERSION = "0.1.0"


def current_version() -> str:
    try:
        root = Path(__file__).resolve().parent.parent
        text = (root / "pyproject.toml").read_text(encoding="utf-8")
        match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
        if match:
            return match.group(1)
    except OSError:
        pass
    return _FALLBACK_VERSION

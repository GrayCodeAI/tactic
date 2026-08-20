"""Update checker — Tau update_check.py port (Tau 37a9e43 src/tau_coding/update_check.py), lean-adapted.

Polls PyPI for the newest released ``lean-prover`` version and caches the
result under ``releases.json`` in the config dir so repeated startups don't
hammer the index. Throttled to one check per day.
"""

from __future__ import annotations

import json
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from .paths import ProverPaths
from .version import current_version

CHECK_INTERVAL_SECONDS = 86_400
DEFAULT_PACKAGE_NAME = "lean-prover"


@dataclass(frozen=True, slots=True)
class UpdateInfo:
    """Outcome of one update check (tau parity)."""

    current_version: str
    latest_version: str | None = None
    is_update_available: bool = False
    error: str | None = None


def _parse_version(text: str) -> tuple[int, ...]:
    parts: list[int] = []
    for chunk in text.strip().lstrip("v").split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        if digits:
            parts.append(int(digits))
    return tuple(parts) or (0,)


def should_check() -> bool:
    """True when the cached check is stale or missing."""
    cache = _cache_path()
    if not cache.exists():
        return True
    try:
        data = json.loads(cache.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return True
    checked_at = float(data.get("checked_at") or 0)
    return time.time() - checked_at >= CHECK_INTERVAL_SECONDS


def _cache_path() -> Path:
    return ProverPaths().config_dir / "releases.json"


def _fetch_latest(package: str, timeout: float = 10.0) -> str | None:
    url = f"https://pypi.org/pypi/{package}/json"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (json.JSONDecodeError, OSError, ValueError):
        return None
    info = data.get("info") if isinstance(data, dict) else None
    if isinstance(info, dict):
        version = info.get("version")
        if isinstance(version, str) and version.strip():
            return version.strip()
    return None


def check_for_updates(package: str = DEFAULT_PACKAGE_NAME, *, force: bool = False) -> UpdateInfo:
    """Check PyPI for a newer release; returns cached data when throttled."""
    current = current_version()
    cache = _cache_path()
    latest: str | None = None
    error: str | None = None

    if force or should_check():
        latest = _fetch_latest(package)
        if latest is None:
            error = "could not fetch release information"
        try:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(
                json.dumps(
                    {"checked_at": time.time(), "latest_version": latest, "package": package},
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
        except OSError:
            pass
    else:
        try:
            data = json.loads(cache.read_text(encoding="utf-8"))
            latest = data.get("latest_version")
        except (json.JSONDecodeError, OSError):
            pass

    is_update_available = bool(latest) and _parse_version(str(latest)) > _parse_version(current)
    return UpdateInfo(
        current_version=current,
        latest_version=latest,
        is_update_available=is_update_available,
        error=error,
    )

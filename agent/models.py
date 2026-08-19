"""Model profiles — persisted model/endpoint config, managed from the TUI.

A ``ModelProfile`` binds a model name (the id sent to the endpoint) to an
optional endpoint (``base_url`` + ``api_key``) plus optional overrides for the
context window and per-1M-token costs. Profiles live in
``~/.prover/models.json`` (or ``$PROVER_CONFIG_DIR/models.json``).

Resolution order (lowest to highest precedence):
  1. the store's ``active`` profile name, when ``PROVER_MODEL`` is unset;
  2. ``PROVER_MODEL`` env var (headless/CI escape hatch, always wins);
  3. for endpoint/key/context/cost lookups, a matching profile's overrides
     win over ``OPENAI_BASE_URL`` / ``OPENAI_API_KEY`` / ``PROVER_CONTEXT_WINDOW``
     / the hardcoded tables in ``llm.py``.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from .paths import ProverPaths

DEFAULT_MODEL = "gpt-4o"


@dataclass(frozen=True, slots=True)
class ModelProfile:
    """One named model profile (immutable value).

    Empty ``base_url`` / ``api_key`` mean "use the env endpoint/key".
    ``None`` overrides mean "no override" (env/hardcoded table wins).
    """

    name: str
    label: str = ""
    base_url: str = ""
    api_key: str = ""
    context_window: int | None = None
    cost_in: float | None = None
    cost_out: float | None = None

    @property
    def display(self) -> str:
        return self.label or self.name

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "label": self.label,
            "base_url": self.base_url,
            "api_key": self.api_key,
            "context_window": self.context_window,
            "cost_in": self.cost_in,
            "cost_out": self.cost_out,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ModelProfile:
        name = str(data.get("name") or "").strip()
        if not name:
            raise ValueError("model profile requires a name")

        def _int(value, default=None) -> int | None:
            if value in (None, ""):
                return default
            return int(value)

        def _float(value, default=None) -> float | None:
            if value in (None, ""):
                return default
            return float(value)

        return cls(
            name=name,
            label=str(data.get("label") or "").strip(),
            base_url=str(data.get("base_url") or "").strip(),
            api_key=str(data.get("api_key") or ""),
            context_window=_int(data.get("context_window")),
            cost_in=_float(data.get("cost_in")),
            cost_out=_float(data.get("cost_out")),
        )


def models_store_path() -> Path:
    """Where model profiles persist (``~/.prover/models.json``)."""
    return ProverPaths().config_dir / "models.json"


def load_profiles() -> list[ModelProfile]:
    """All configured profiles, in stored order (empty when unset/corrupt)."""
    path = models_store_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, TypeError):
        return []
    profiles: list[ModelProfile] = []
    for entry in data.get("profiles", []) if isinstance(data, dict) else []:
        if not isinstance(entry, dict):
            continue
        try:
            profiles.append(ModelProfile.from_dict(entry))
        except (ValueError, TypeError):
            continue
    return profiles


def save_store(active: str = "", profiles: list[ModelProfile] | None = None) -> None:
    """Persist the active profile name and the profile list."""
    path = models_store_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return
    body = {
        "active": active or "",
        "profiles": [p.to_dict() for p in (profiles or load_profiles())],
    }
    try:
        path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass


def _stored_active() -> str:
    path = models_store_path()
    if not path.exists():
        return ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, TypeError):
        return ""
    return str(data.get("active") or "") if isinstance(data, dict) else ""


def resolved_model_name() -> str:
    """The active model name: env ``PROVER_MODEL`` > store ``active`` > default."""
    env = os.environ.get("PROVER_MODEL")
    if env:
        return env
    active = _stored_active()
    if active:
        return active
    return DEFAULT_MODEL


def profile_for(name: str) -> ModelProfile | None:
    """The profile whose name equals ``name``, or None."""
    for profile in load_profiles():
        if profile.name == name:
            return profile
    return None


def active_profile() -> ModelProfile | None:
    """Profile matching the resolved active model name (env override wins)."""
    return profile_for(resolved_model_name())

"""Provider/model catalog loading — Tau catalog_loader.py port, lean-adapted.

The builtin catalog describes the provider fleet lean-prover knows out of the
box (same names as ``agent/catalog.py`` plus Tau's qwen/deepseek entries).  A
user ``catalog.toml`` overlay can add or override entries; persisted entries
land in ``providers.json`` via provider_config.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .catalog import load_catalog
from .paths import ProverPaths

BUILTIN_PROVIDER_CATALOG = {
    "qwen": {
        "provider": "qwen",
        "base_url": "http://localhost:8000/v1",
        "api_key_env": "OPENAI_API_KEY",
        "models": [
            {"name": "qwen3-8b", "context_window": 32768, "cost_in": 0.0, "cost_out": 0.0, "thinking": "off"},
        ],
    },
    "openai": {
        "provider": "openai",
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
        "models": [
            {"name": "gpt-4o", "context_window": 128000, "cost_in": 5.0, "cost_out": 15.0, "thinking": "off"},
            {"name": "gpt-4o-mini", "context_window": 128000, "cost_in": 0.15, "cost_out": 0.6, "thinking": "off"},
        ],
    },
    "anthropic": {
        "provider": "anthropic",
        "base_url": "https://api.anthropic.com",
        "api_key_env": "ANTHROPIC_API_KEY",
        "models": [
            {"name": "claude-sonnet-4", "context_window": 200000, "cost_in": 3.0, "cost_out": 15.0, "thinking": "low"},
        ],
    },
    "deepseek": {
        "provider": "deepseek",
        "base_url": "https://api.deepseek.com/v1",
        "api_key_env": "DEEPSEEK_API_KEY",
        "models": [
            {"name": "deepseek-chat", "context_window": 128000, "cost_in": 0.14, "cost_out": 0.28, "thinking": "off"},
        ],
    },
    "mistral": {
        "provider": "mistral",
        "base_url": "https://api.mistral.ai/v1",
        "api_key_env": "MISTRAL_API_KEY",
        "models": [
            {"name": "mistral-large", "context_window": 128000, "cost_in": 2.0, "cost_out": 6.0, "thinking": "off"},
        ],
    },
}


def builtin_catalog() -> dict[str, Any]:
    """Return the builtin provider catalog (deep copy so callers may mutate)."""
    import copy

    return copy.deepcopy(BUILTIN_PROVIDER_CATALOG)


def _catalog_overlay_path() -> Path | None:
    override = os.environ.get("PROVER_CATALOG_PATH")
    if override:
        return Path(override)
    local = Path.cwd() / ".prover" / "catalog.toml"
    if local.exists():
        return local
    user = ProverPaths().config_dir / "catalog.toml"
    if user.exists():
        return user
    return None


def effective_catalog() -> dict[str, Any]:
    """Builtin catalog merged with a user ``catalog.toml`` overlay, if any."""
    catalog = builtin_catalog()
    overlay = _catalog_overlay_path()
    if overlay is not None and overlay.exists():
        merged = load_catalog(overlay)
        if isinstance(merged, dict):
            for provider, entry in merged.items():
                if provider == "models" or provider == "providers":
                    continue
                catalog[provider] = entry
    return catalog


def provider_config_from_catalog_entry(provider: str, entry: dict[str, Any]) -> dict[str, Any] | None:
    """Build a provider config dict from a catalog entry (tau parity)."""
    if not isinstance(entry, dict):
        return None
    base_url = str(entry.get("base_url") or "")
    env_key = str(entry.get("api_key_env") or "OPENAI_API_KEY")
    return {
        "name": provider,
        "kind": str(entry.get("kind") or "openai_compatible"),
        "base_url": base_url,
        "env_key": env_key,
        "api_key": None,
        "models": entry.get("models", []),
    }

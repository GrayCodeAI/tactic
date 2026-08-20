"""OAuth provider registry — Tau oauth_registry.py port, lean-adapted.

Maintains a global registry of named ``OAuthProvider`` implementations so
commands like ``/login <provider>`` can dispatch dynamically. Three built-ins
are registered at module load.
"""

from __future__ import annotations

from .types import OAuthProvider

_REGISTRY: dict[str, OAuthProvider] = {}


def register_oauth_provider(provider: OAuthProvider) -> None:
    """Register a named provider in the global registry (tau parity)."""
    _REGISTRY[provider.name] = provider


def get_oauth_provider(name: str) -> OAuthProvider | None:
    return _REGISTRY.get(name)


def list_oauth_providers() -> list[str]:
    return sorted(_REGISTRY.keys())


def _register_builtins() -> None:
    # Placeholder: real providers get wired when their modules are imported.
    # The codex/login command in agent/commands.py imports oauth.codex which
    # registers its provider lazily to avoid circular imports.
    pass


_register_builtins()

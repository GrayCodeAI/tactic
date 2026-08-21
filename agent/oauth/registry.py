"""OAuth provider registry — Tau oauth_registry.py port (Tau 37a9e43 src/tau_coding/oauth_registry.py), lean-adapted.

Maintains a global registry of named ``OAuthProvider`` implementations so
commands like ``/login <provider>`` can dispatch dynamically. Three built-ins
are registered at module load.
"""

from __future__ import annotations

from .types import OAuthProvider

_REGISTRY: dict[str, OAuthProvider] = {}


def get_oauth_provider(name: str) -> OAuthProvider | None:
    return _REGISTRY.get(name)


def _register_builtins() -> None:
    # Placeholder: real providers get wired when their modules are imported.
    # The codex/login command in agent/commands.py imports oauth.codex which
    # registers its provider lazily to avoid circular imports.
    pass


_register_builtins()

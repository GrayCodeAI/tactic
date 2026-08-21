"""OAuth package — Tau oauth* modules port, lean-adapted.

Facade re-exports the credential type and routes to provider-specific flows
via ``login_*`` helpers.
"""

from __future__ import annotations

from ..credentials import OAuthCredential
from .types import OAuthPrompt, OAuthProvider


def get_provider(name: str) -> OAuthProvider | None:
    from .registry import get_oauth_provider
    return get_oauth_provider(name)


__all__ = [
    "OAuthCredential",
    "OAuthPrompt",
    "OAuthProvider",
    "get_provider",
]

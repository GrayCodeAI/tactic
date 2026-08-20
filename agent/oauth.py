from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OAuthToken:
    access_token: str
    refresh_token: str | None = None
    expires_at: float | None = None


def get_oauth_token(provider: str) -> OAuthToken | None:
    return None

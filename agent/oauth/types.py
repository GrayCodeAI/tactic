"""OAuth type protocols — Tau oauth_types.py port."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class OAuthPrompt:
    """One step of an interactive OAuth login (tau OAuthPrompt)."""

    kind: str  # "url" | "input" | "confirm" | "wait"
    text: str
    url: str | None = None


@runtime_checkable
class OAuthProvider(Protocol):
    """Protocol all login providers implement (tau OAuthProvider)."""

    name: str

    async def login(self, prompt_cb: Callable[[OAuthPrompt], Any]) -> Any: ...

    async def refresh(self, credential: Any) -> Any | None: ...


LoginCallback = Callable[[OAuthPrompt], Awaitable[Any]]

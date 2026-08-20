from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol


class CancellationToken(Protocol):
    def is_cancelled(self) -> bool: ...


class ModelProvider(Protocol):
    def stream_response(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict],
        tools: list[dict],
        signal: CancellationToken | None = None,
        session_id: str | None = None,
    ) -> AsyncIterator[dict]: ...

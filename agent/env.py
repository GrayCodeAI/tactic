from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OpenAICompatibleConfig:
    base_url: str | None = None
    api_key: str | None = None

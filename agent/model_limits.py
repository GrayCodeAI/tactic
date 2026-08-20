from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class RuntimeModelLimits:
    context_window: int
    max_output_tokens: int | None = None
    effective_context_window_percent: int = 100
    auto_compact_token_limit: int | None = None

    def __post_init__(self) -> None:
        if self.context_window <= 0:
            raise ValueError("context_window must be positive")
        if self.max_output_tokens is not None and self.max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be positive")
        if not 1 <= self.effective_context_window_percent <= 100:
            raise ValueError("effective_context_window_percent must be between 1 and 100")
        if self.auto_compact_token_limit is not None and self.auto_compact_token_limit <= 0:
            raise ValueError("auto_compact_token_limit must be positive")

    @property
    def effective_context_window(self) -> int:
        return max(1, self.context_window * self.effective_context_window_percent // 100)

    @property
    def effective_auto_compact_token_limit(self) -> int:
        default_limit = max(1, self.context_window * 9 // 10)
        if self.auto_compact_token_limit is None:
            return min(default_limit, self.effective_context_window)
        return min(self.auto_compact_token_limit, self.effective_context_window)


@runtime_checkable
class ModelLimitsProvider(Protocol):
    async def discover_model_limits(self, model: str) -> RuntimeModelLimits | None: ...

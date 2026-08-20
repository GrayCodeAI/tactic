from __future__ import annotations

from collections.abc import AsyncIterator

from .provider_events import AssistantMessageEvent


async def canonicalize_provider_stream(stream: AsyncIterator[AssistantMessageEvent]) -> AsyncIterator[AssistantMessageEvent]:
    async for event in stream:
        yield event

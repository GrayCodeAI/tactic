from __future__ import annotations

from collections.abc import AsyncIterator

from ..messages import AssistantMessage, TextContent
from ..provider_events import AssistantDoneEvent, AssistantStartEvent


class FakeProvider:
    def __init__(self, text: str = "fake response") -> None:
        self.text = text

    async def stream_response(self, *, model: str, system: str, messages: list, tools: list, signal=None, session_id=None) -> AsyncIterator:
        msg = AssistantMessage(content=[TextContent(text=self.text)], model=model)
        yield AssistantStartEvent(partial=msg)
        yield AssistantDoneEvent(reason="stop", message=msg)

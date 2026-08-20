from __future__ import annotations

import os
from collections.abc import AsyncIterator

from openai import OpenAI, Timeout

from ..messages import AssistantMessage, TextContent
from ..provider import CancellationToken
from ..provider_events import AssistantDoneEvent, AssistantStartEvent


class OpenAICompatibleProvider:
    def __init__(self, base_url: str | None = None, api_key: str | None = None) -> None:
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "unused")
        self._client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=Timeout(connect=15.0, read=900.0, write=15.0, pool=15.0),
            max_retries=2,
        )

    async def stream_response(
        self,
        *,
        model: str,
        system: str,
        messages: list,
        tools: list,
        signal: CancellationToken | None = None,
        session_id: str | None = None,
    ) -> AsyncIterator:
        import asyncio

        if signal and signal.is_cancelled():
            return
        ov_messages = [{"role": "system", "content": system}]
        for m in messages:
            if hasattr(m, "role") and hasattr(m, "content"):
                ov_messages.append({"role": m.role, "content": m.text if hasattr(m, "text") else str(m.content)})
            elif isinstance(m, dict):
                ov_messages.append(m)
        try:
            resp = await asyncio.to_thread(
                self._client.chat.completions.create,
                model=model,
                messages=ov_messages,
                temperature=0.2,
                max_tokens=4096,
            )
            content = resp.choices[0].message.content or ""
            msg = AssistantMessage(content=[TextContent(text=content)], model=model)
            yield AssistantStartEvent(partial=msg)
            yield AssistantDoneEvent(reason="stop", message=msg)
        except Exception as e:  # noqa: BLE001
            from ..provider_events import AssistantErrorEvent

            err_msg = AssistantMessage(content=[], model=model, stop_reason="error", error_message=str(e))
            yield AssistantErrorEvent(reason="error", error=err_msg)

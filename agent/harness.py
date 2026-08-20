"""Stateful reusable agent harness — Tau 37a9e43 port, lean-adapted."""
from __future__ import annotations

from collections import deque
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import suppress
from dataclasses import dataclass, field
from inspect import isawaitable
from typing import Literal, TypeAlias

try:
    from .events import AgentEvent  # type: ignore
except ImportError:
    AgentEvent = object  # type: ignore

try:
    from .messages import (
        AgentMessage,
        AssistantMessage,
        TextContent,
        ToolResultMessage,
        UserMessage,
    )
except ImportError:
    AgentMessage = object  # type: ignore
    AssistantMessage = object  # type: ignore
    TextContent = object  # type: ignore
    ToolResultMessage = object  # type: ignore
    UserMessage = object  # type: ignore

try:
    from .provider import ModelProvider
    from .tools import AgentTool
except ImportError:
    ModelProvider = object  # type: ignore
    AgentTool = object  # type: ignore

EventListener = Callable[[AgentEvent], Awaitable[None] | None]
QueueMode: TypeAlias = Literal["one_at_a_time", "all"]  # type: ignore[no-redef]


@dataclass(frozen=True, slots=True)
class QueuedMessages:
    steering: tuple[AgentMessage, ...] = ()  # type: ignore
    follow_up: tuple[AgentMessage, ...] = ()  # type: ignore

    @property
    def count(self) -> int:
        return len(self.steering) + len(self.follow_up)


@dataclass(slots=True)
class AgentHarnessConfig:
    provider: ModelProvider  # type: ignore
    model: str
    system: str
    tools: list[AgentTool] = field(default_factory=list)  # type: ignore
    max_turns: int | None = None
    queue_mode: QueueMode = "one_at_a_time"  # type: ignore
    session_id: str | None = None
    before_tool_call: Callable | None = None
    after_tool_call: Callable | None = None


class SimpleCancellationToken:
    def __init__(self) -> None:
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def is_cancelled(self) -> bool:
        return self._cancelled


class AgentHarness:
    def __init__(self, config: AgentHarnessConfig, *, messages: Sequence[AgentMessage] = ()) -> None:  # type: ignore
        self._config = config
        self._messages = list(messages)
        self._listeners: list[EventListener] = []
        self._current_signal: SimpleCancellationToken | None = None
        self._running = False
        self._steering_queue: deque[AgentMessage] = deque()  # type: ignore
        self._follow_up_queue: deque[AgentMessage] = deque()  # type: ignore

    @property
    def messages(self) -> tuple[AgentMessage, ...]:  # type: ignore
        return tuple(self._messages)

    @property
    def config(self) -> AgentHarnessConfig:
        return self._config

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def queued_messages(self) -> QueuedMessages:
        return QueuedMessages(tuple(self._steering_queue), tuple(self._follow_up_queue))

    @property
    def pending_message_count(self) -> int:
        return self.queued_messages.count

    def has_queued_messages(self) -> bool:
        return bool(self._steering_queue or self._follow_up_queue)

    def append_message(self, message: AgentMessage) -> None:  # type: ignore
        self._messages.append(message)

    def replace_messages(self, messages: Sequence[AgentMessage]) -> None:  # type: ignore
        self._messages = list(messages)

    def subscribe(self, listener: EventListener) -> Callable[[], None]:
        self._listeners.append(listener)

        def unsubscribe() -> None:
            with suppress(ValueError):
                self._listeners.remove(listener)

        return unsubscribe

    def cancel(self) -> None:
        if self._current_signal is not None:
            self._current_signal.cancel()

    def steer(self, content: str) -> QueuedMessages:
        return self.steer_message(UserMessage(content=content))  # type: ignore

    def steer_message(self, message: AgentMessage) -> QueuedMessages:  # type: ignore
        self._steering_queue.append(message)
        return self.queued_messages

    def follow_up(self, content: str) -> QueuedMessages:
        return self.follow_up_message(UserMessage(content=content))  # type: ignore

    def follow_up_message(self, message: AgentMessage) -> QueuedMessages:  # type: ignore
        self._follow_up_queue.append(message)
        return self.queued_messages

    def clear_queues(self) -> QueuedMessages:
        snapshot = self.queued_messages
        self._steering_queue.clear()
        self._follow_up_queue.clear()
        return snapshot

    def pop_latest_follow_up(self) -> AgentMessage | None:  # type: ignore
        return self._follow_up_queue.pop() if self._follow_up_queue else None

    def pop_latest_steering(self) -> AgentMessage | None:  # type: ignore
        return self._steering_queue.pop() if self._steering_queue else None

    def prompt_message(self, message: AgentMessage) -> AsyncIterator[AgentEvent]:  # type: ignore
        self._ensure_not_running()
        self._running = True
        return self._run(prompts=(message,))

    def prompt(self, content: str) -> AsyncIterator[AgentEvent]:  # type: ignore
        return self.prompt_message(UserMessage(content=content))  # type: ignore

    def continue_(self) -> AsyncIterator[AgentEvent]:  # type: ignore
        self._ensure_not_running()
        self._running = True
        return self._run()

    async def _run(self, *, prompts: Sequence[AgentMessage] = ()) -> AsyncIterator[AgentEvent]:  # type: ignore
        signal = SimpleCancellationToken()
        self._current_signal = signal
        try:
            # lean-adapted: repair not needed for dict history, but keep hook
            for event in []:  # stub: lean prover uses prove() not run_agent_loop
                await self._notify(event)  # type: ignore
                yield event
        finally:
            if self._current_signal is signal:
                self._current_signal = None
            self._running = False

    async def _notify(self, event: AgentEvent) -> None:  # type: ignore
        for listener in list(self._listeners):
            result = listener(event)
            if isawaitable(result):
                await result

    def _ensure_not_running(self) -> None:
        if self._running:
            raise RuntimeError("AgentHarness is already running; use steer() or follow_up() to queue messages.")

    def _drain_steering_messages(self) -> tuple[AgentMessage, ...]:  # type: ignore
        return self._drain_queue(self._steering_queue)

    def _drain_follow_up_messages(self) -> tuple[AgentMessage, ...]:  # type: ignore
        return self._drain_queue(self._follow_up_queue)

    def _drain_queue(self, queue: deque[AgentMessage]) -> tuple[AgentMessage, ...]:  # type: ignore
        if not queue:
            return ()
        if self._config.queue_mode == "all":
            messages = tuple(queue)
            queue.clear()
            return messages
        return (queue.popleft(),)

    def append_interrupted_tool_results(self) -> int:
        before = len(self._messages)
        self._append_interrupted_tool_results()
        return len(self._messages) - before

    def _append_interrupted_tool_results(self) -> None:
        try:
            returned_ids = {m.tool_call_id for m in self._messages if hasattr(m, "tool_call_id")}  # type: ignore
            for m in tuple(self._messages):
                if not hasattr(m, "tool_calls"):
                    continue
                for call in getattr(m, "tool_calls", ()):  # type: ignore
                    cid = getattr(call, "id", "")
                    if cid in returned_ids:
                        continue
                    returned_ids.add(cid)
                    self._messages.append(ToolResultMessage(tool_call_id=cid, tool_name=getattr(call, "name", ""), content=[TextContent(text="Tool call interrupted by user")], is_error=True))  # type: ignore
        except Exception:  # noqa: BLE001, S110
            pass

"""In-process asynchronous message bus with traceable history."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from ai_education.domain.protocols import AgentMessage

Subscriber = Callable[[AgentMessage], Awaitable[None]]


class AgentMessageBus:
    """Publish immutable protocol messages to subscribers and an audit history."""

    def __init__(self, *, max_history: int = 10_000) -> None:
        self._subscribers: list[Subscriber] = []
        self._history: list[AgentMessage] = []
        self._max_history = max_history
        self._lock = asyncio.Lock()

    def subscribe(self, subscriber: Subscriber) -> Callable[[], None]:
        self._subscribers.append(subscriber)

        def unsubscribe() -> None:
            if subscriber in self._subscribers:
                self._subscribers.remove(subscriber)

        return unsubscribe

    async def publish(self, message: AgentMessage) -> None:
        immutable = message.model_copy(deep=True)
        async with self._lock:
            self._history.append(immutable)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history :]
        if self._subscribers:
            await asyncio.gather(
                *(subscriber(immutable.model_copy(deep=True)) for subscriber in self._subscribers),
                return_exceptions=True,
            )

    def history(self, *, trace_id: str | None = None) -> tuple[AgentMessage, ...]:
        messages = self._history
        if trace_id:
            messages = [message for message in messages if message.trace_id == trace_id]
        return tuple(message.model_copy(deep=True) for message in messages)

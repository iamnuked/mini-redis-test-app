from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from internal.arena.gateway.models import EventEnvelope


@dataclass
class ArenaEventBus:
    _subscribers: set[asyncio.Queue[EventEnvelope]] = field(default_factory=set)

    async def publish(self, envelope: EventEnvelope) -> None:
        for subscriber in list(self._subscribers):
            subscriber.put_nowait(envelope)

    def subscribe(self) -> asyncio.Queue[EventEnvelope]:
        queue: asyncio.Queue[EventEnvelope] = asyncio.Queue()
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[EventEnvelope]) -> None:
        self._subscribers.discard(queue)

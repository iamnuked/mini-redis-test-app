from __future__ import annotations

from dataclasses import dataclass, field

from internal.arena.gateway.models import EventEnvelope


@dataclass
class EventHistory:
    max_events: int = 200
    _events: list[EventEnvelope] = field(default_factory=list)

    def append(self, envelope: EventEnvelope) -> None:
        self._events.append(envelope)
        self._events = self._events[-self.max_events :]

    def snapshot(self) -> list[EventEnvelope]:
        return list(self._events)

    def clear(self) -> None:
        self._events.clear()

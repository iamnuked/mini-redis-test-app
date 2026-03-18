from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from internal.arena.gateway.models import EventEnvelope

router = APIRouter()


def encode_sse(envelope: EventEnvelope) -> str:
    return f"event: arena\ndata: {json.dumps(envelope.to_dict())}\n\n"


@router.get("/api/events")
async def stream_events(request: Request) -> StreamingResponse:
    event_bus = request.app.state.event_bus
    event_history = request.app.state.event_history

    async def event_stream():
        for envelope in event_history.snapshot():
            yield encode_sse(envelope)

        queue = event_bus.subscribe()
        try:
            while True:
                if await request.is_disconnected():
                    break

                try:
                    envelope = await asyncio.wait_for(queue.get(), timeout=15)
                    yield encode_sse(envelope)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            event_bus.unsubscribe(queue)

    return StreamingResponse(event_stream(), media_type="text/event-stream")

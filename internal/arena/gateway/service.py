from __future__ import annotations

import asyncio
import inspect
from uuid import uuid4

from internal.arena.events.bus import ArenaEventBus
from internal.arena.events.history import EventHistory
from internal.arena.gateway.models import (
    ArenaRequest,
    EventEnvelope,
    ExecutionResult,
    ManualCommandInput,
    MessageResponse,
)
from internal.arena.gateway.lane_client import ArenaLaneExecutor
from internal.arena.gateway.result_normalizer import build_execution


class ArenaGatewayService:
    def __init__(
        self,
        redis_lane: ArenaLaneExecutor,
        db_only_lane: ArenaLaneExecutor,
        event_bus: ArenaEventBus,
        event_history: EventHistory,
    ) -> None:
        self._redis_lane = redis_lane
        self._db_only_lane = db_only_lane
        self._event_bus = event_bus
        self._event_history = event_history
        self._known_keys: set[str] = set()

    async def execute_manual_command(self, command_input: ManualCommandInput) -> ExecutionResult:
        request = self._build_request(mode="manual", command_input=command_input)
        return await self._execute_request(request, event_type="manual_command_completed")

    async def execute_scenario_command(self, command_input: ManualCommandInput) -> ExecutionResult:
        request = self._build_request(mode="scenario", command_input=command_input)
        return await self._execute_request(request, event_type="scenario_execution_completed")

    async def publish_message(self, event_type: str, message: str) -> MessageResponse:
        response = MessageResponse(message=message)
        await self._publish(event_type=event_type, payload=response.to_dict())
        return response

    async def reset_state(self) -> None:
        keys = tuple(self._known_keys)
        await asyncio.gather(
            self._clear_lane(self._redis_lane, keys),
            self._clear_lane(self._db_only_lane, keys),
        )
        self._known_keys.clear()

    async def healthcheck(self) -> dict:
        redis_lane = await self._lane_health(self._redis_lane, "redis_db")
        db_only_lane = await self._lane_health(self._db_only_lane, "db_only")
        status = (
            "ok"
            if redis_lane.get("status") == "ok" and db_only_lane.get("status") == "ok"
            else "degraded"
        )
        return {
            "status": status,
            "gateway": {
                "status": "ok",
                "tracked_keys": len(self._known_keys),
                "retained_events": len(self._event_history.snapshot()),
            },
            "redis_lane": redis_lane,
            "db_only_lane": db_only_lane,
        }

    def _build_request(self, mode: str, command_input: ManualCommandInput) -> ArenaRequest:
        return ArenaRequest(
            request_id=f"req-{uuid4().hex[:8]}",
            mode=mode,
            command=command_input.command,
            key=command_input.key,
            value=command_input.value,
            ttl_enabled=command_input.ttl_enabled,
        )

    async def _execute_request(self, request: ArenaRequest, event_type: str) -> ExecutionResult:
        self._known_keys.add(request.key)
        redis_result, db_only_result = await asyncio.gather(
            self._redis_lane.execute(request),
            self._db_only_lane.execute(request),
        )
        execution = build_execution(request, redis_result, db_only_result)
        await self._publish(event_type=event_type, payload=execution.to_dict())
        return execution

    async def _publish(self, event_type: str, payload: dict) -> None:
        envelope = EventEnvelope(type=event_type, payload=payload)
        self._event_history.append(envelope)
        await self._event_bus.publish(envelope)

    async def _clear_lane(self, lane_executor: ArenaLaneExecutor, keys: tuple[str, ...]) -> None:
        clear_result = lane_executor.clear(keys)
        if inspect.isawaitable(clear_result):
            await clear_result

    async def _lane_health(self, lane_executor: ArenaLaneExecutor, lane_name: str) -> dict:
        health = getattr(lane_executor, "health", None)
        if health is None:
            return {"lane": lane_name, "status": "unknown"}
        try:
            result = health()
            if inspect.isawaitable(result):
                return await result
            return result
        except Exception as exc:
            return {"lane": lane_name, "status": "error", "error": str(exc)}

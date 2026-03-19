from __future__ import annotations

import asyncio
import inspect
from uuid import uuid4

from internal.arena.control_profiles import (
    DEFAULT_MEMORY_PROFILE,
    DEFAULT_TTL_PROFILE,
    MEMORY_PROFILES,
    TTL_PROFILES,
)
from internal.arena.events.bus import ArenaEventBus
from internal.arena.events.history import EventHistory
from internal.arena.gateway.models import (
    ArenaRequest,
    EventEnvelope,
    ExecutionResult,
    ManualCommandInput,
    MessageResponse,
    SeedStateInput,
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
        self._selected_memory_profile = DEFAULT_MEMORY_PROFILE
        self._selected_ttl_profile: str | None = DEFAULT_TTL_PROFILE
        self._memory_locked = False

    async def initialize(self) -> None:
        await self._apply_selected_memory_profile()

    async def execute_manual_command(self, command_input: ManualCommandInput) -> ExecutionResult:
        self._lock_memory_profile()
        request = self._build_request(mode="manual", command_input=command_input)
        return await self._execute_request(request, event_type="manual_command_completed")

    async def execute_scenario_command(self, command_input: ManualCommandInput) -> ExecutionResult:
        self._lock_memory_profile()
        request = self._build_request(mode="scenario", command_input=command_input)
        return await self._execute_request(request, event_type="scenario_execution_completed")

    async def publish_message(self, event_type: str, message: str) -> MessageResponse:
        response = MessageResponse(message=message)
        await self._publish(event_type=event_type, payload=response.to_dict())
        return response

    async def reset_state(self) -> None:
        await asyncio.gather(
            self._clear_lane(self._redis_lane, (), full_reset=True),
            self._clear_lane(self._db_only_lane, (), full_reset=True),
        )
        self._known_keys.clear()
        self._memory_locked = False
        await self._apply_selected_memory_profile()

    async def seed_state(
        self,
        documents: dict[str, str],
        *,
        warm_cache: bool = False,
        ttl_enabled: bool = False,
        ttl_seconds: float | None = None,
    ) -> None:
        seed_input = SeedStateInput(
            documents=documents,
            warm_cache=warm_cache,
            ttl_enabled=ttl_enabled,
            ttl_seconds=ttl_seconds,
        )
        await asyncio.gather(
            self._seed_lane(self._redis_lane, seed_input),
            self._seed_lane(self._db_only_lane, seed_input),
        )
        self._known_keys.update(documents.keys())

    async def set_memory_profile(self, profile_key: str) -> dict:
        if profile_key not in MEMORY_PROFILES:
            raise ValueError(f"Unsupported memory profile: {profile_key}")
        if self._memory_locked:
            raise RuntimeError("Memory profile is locked until the next reset.")
        self._selected_memory_profile = profile_key
        lane_response = await self._apply_selected_memory_profile()
        return {
            "selected": self._selected_memory_profile,
            "locked": self._memory_locked,
            "profile": MEMORY_PROFILES[self._selected_memory_profile].to_dict(),
            "lane": lane_response,
        }

    async def set_ttl_profile(self, profile_key: str | None) -> dict:
        if profile_key is None:
            self._selected_ttl_profile = None
            return {
                "selected": None,
                "seconds": None,
                "profile": None,
            }
        if profile_key not in TTL_PROFILES:
            raise ValueError(f"Unsupported TTL profile: {profile_key}")
        self._selected_ttl_profile = profile_key
        profile = TTL_PROFILES[self._selected_ttl_profile]
        return {
            "selected": self._selected_ttl_profile,
            "seconds": profile.ttl_seconds,
            "profile": profile.to_dict(),
        }

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
            "controls": {
                "memory": {
                    "selected": self._selected_memory_profile,
                    "locked": self._memory_locked,
                    "profiles": [profile.to_dict() for profile in MEMORY_PROFILES.values()],
                },
                "ttl": {
                    "selected": self._selected_ttl_profile,
                    "seconds": self.selected_ttl_seconds(),
                    "profiles": [profile.to_dict() for profile in TTL_PROFILES.values()],
                },
            },
            "redis_lane": redis_lane,
            "db_only_lane": db_only_lane,
        }

    def _build_request(self, mode: str, command_input: ManualCommandInput) -> ArenaRequest:
        ttl_enabled = command_input.ttl_enabled
        ttl_seconds = command_input.ttl_seconds
        if command_input.ttl_enabled and ttl_seconds is None:
            ttl_seconds = self.selected_ttl_seconds()
            if ttl_seconds is None:
                ttl_enabled = False
        return ArenaRequest(
            request_id=f"req-{uuid4().hex[:8]}",
            mode=mode,
            command=command_input.command,
            key=command_input.key,
            field=command_input.field,
            value=command_input.value,
            ttl_enabled=ttl_enabled,
            ttl_seconds=ttl_seconds,
        )

    def selected_ttl_seconds(self) -> float | None:
        if self._selected_ttl_profile is None:
            return None
        return TTL_PROFILES[self._selected_ttl_profile].ttl_seconds

    def _lock_memory_profile(self) -> None:
        self._memory_locked = True

    async def _apply_selected_memory_profile(self) -> dict | None:
        configure_memory = getattr(self._redis_lane, "configure_memory", None)
        if configure_memory is None:
            return None
        profile = MEMORY_PROFILES[self._selected_memory_profile]
        result = configure_memory(
            profile_key=profile.key,
            max_memory_bytes=profile.max_memory_bytes,
        )
        if inspect.isawaitable(result):
            return await result
        return result

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

    async def _clear_lane(
        self,
        lane_executor: ArenaLaneExecutor,
        keys: tuple[str, ...],
        *,
        full_reset: bool = False,
    ) -> None:
        clear_result = lane_executor.clear(keys, full_reset=full_reset)
        if inspect.isawaitable(clear_result):
            await clear_result

    async def _seed_lane(
        self,
        lane_executor: ArenaLaneExecutor,
        seed_input: SeedStateInput,
    ) -> None:
        seed_result = lane_executor.seed(seed_input)
        if inspect.isawaitable(seed_result):
            await seed_result

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

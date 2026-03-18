from __future__ import annotations

import asyncio

from internal.arena.events.history import EventHistory
from internal.arena.gateway.models import ManualCommandInput, MessageResponse, ScenarioRunInput
from internal.arena.gateway.service import ArenaGatewayService
from internal.arena.lane.cache_policy import default_ttl_seconds
from internal.arena.scenario.hot_key import build_hot_key_plan
from internal.arena.scenario.reset import RESET_MESSAGE
from internal.arena.scenario.ttl_expiry import build_ttl_expiry_plan


class ArenaScenarioRunner:
    def __init__(
        self,
        gateway_service: ArenaGatewayService,
        event_history: EventHistory,
    ) -> None:
        self._gateway_service = gateway_service
        self._event_history = event_history
        self._tasks: set[asyncio.Task[None]] = set()

    async def run(self, scenario_input: ScenarioRunInput) -> MessageResponse:
        task = asyncio.create_task(self._run_plan(scenario_input))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return await self._gateway_service.publish_message(
            event_type="scenario_accepted",
            message=f"Scenario accepted: {scenario_input.scenario_id}",
        )

    async def reset(self) -> MessageResponse:
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()
        await self._gateway_service.reset_state()
        self._event_history.clear()
        return await self._gateway_service.publish_message(
            event_type="scenario_reset",
            message=RESET_MESSAGE,
        )

    async def _run_plan(self, scenario_input: ScenarioRunInput) -> None:
        if scenario_input.scenario_id == "hot_key":
            plan = build_hot_key_plan(
                users=scenario_input.users,
                duration_seconds=scenario_input.duration_seconds,
            )
        else:
            plan = build_ttl_expiry_plan(
                users=scenario_input.users,
                duration_seconds=scenario_input.duration_seconds,
                ttl_seconds=default_ttl_seconds(),
            )

        for action in plan:
            if action.delay_seconds > 0:
                await asyncio.sleep(action.delay_seconds)

            await self._gateway_service.execute_scenario_command(
                ManualCommandInput(
                    command=action.command,
                    key=action.key,
                    value=action.value,
                    ttl_enabled=scenario_input.ttl_enabled,
                )
            )

        await self._gateway_service.publish_message(
            event_type="scenario_finished",
            message=f"Scenario finished: {scenario_input.scenario_id}",
        )

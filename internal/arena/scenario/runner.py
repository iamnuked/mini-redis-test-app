from __future__ import annotations

import asyncio

from internal.arena.events.history import EventHistory
from internal.arena.gateway.models import ManualCommandInput, MessageResponse, ScenarioRunInput
from internal.arena.gateway.service import ArenaGatewayService
from internal.arena.scenario.reset import RESET_MESSAGE
from internal.arena.scenario.workloads import build_mixed_plan
from internal.arena.scenario.workloads import build_read_plan
from internal.arena.scenario.workloads import build_write_plan


class ArenaScenarioRunner:
    def __init__(
        self,
        gateway_service: ArenaGatewayService,
        event_history: EventHistory,
    ) -> None:
        self._gateway_service = gateway_service
        self._event_history = event_history
        self._tasks: set[asyncio.Task[None]] = set()
        self._active_labels: set[str] = set()

    async def run(self, scenario_input: ScenarioRunInput) -> MessageResponse:
        label = self._scenario_label(scenario_input)
        self._active_labels.add(label)
        task = asyncio.create_task(self._run_plan(scenario_input))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return await self._gateway_service.publish_message(
            event_type="scenario_accepted",
            message=f"Scenario accepted: {label}",
        )

    async def reset(self) -> MessageResponse:
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()
        self._active_labels.clear()
        await self._gateway_service.reset_state()
        self._event_history.clear()
        return await self._gateway_service.publish_message(
            event_type="scenario_reset",
            message=RESET_MESSAGE,
        )

    def status(self) -> dict[str, str | int | None]:
        active_label = sorted(self._active_labels)[0] if self._active_labels else None
        return {
            "running": bool(self._active_labels),
            "active_label": active_label,
            "active_count": len(self._active_labels),
        }

    async def _run_plan(self, scenario_input: ScenarioRunInput) -> None:
        label = self._scenario_label(scenario_input)
        try:
            if scenario_input.scenario_id == "read":
                plan = build_read_plan(
                    users=scenario_input.users,
                    duration_seconds=scenario_input.duration_seconds,
                    hot_percent=scenario_input.read_hot_percent or 60,
                )
            elif scenario_input.scenario_id == "write":
                plan = build_write_plan(
                    users=scenario_input.users,
                    duration_seconds=scenario_input.duration_seconds,
                )
            else:
                plan = build_mixed_plan(
                    users=scenario_input.users,
                    duration_seconds=scenario_input.duration_seconds,
                )

            if plan.seed_documents:
                await self._gateway_service.seed_state(
                    plan.seed_documents,
                    warm_cache=False,
                    ttl_enabled=False,
                    ttl_seconds=None,
                )

            for action in plan.actions:
                if action.delay_seconds > 0:
                    await asyncio.sleep(action.delay_seconds)

                await self._gateway_service.execute_scenario_command(
                    ManualCommandInput(
                        command=action.command,
                        key=action.key,
                        value=action.value,
                        ttl_enabled=scenario_input.ttl_enabled,
                        ttl_seconds=scenario_input.ttl_seconds,
                    )
                )

            await self._gateway_service.publish_message(
                event_type="scenario_finished",
                message=f"Scenario finished: {label}",
            )
        finally:
            self._active_labels.discard(label)

    def _scenario_label(self, scenario_input: ScenarioRunInput) -> str:
        if scenario_input.scenario_id == "read":
            return f"read {scenario_input.read_hot_percent or 60}%"
        return scenario_input.scenario_id

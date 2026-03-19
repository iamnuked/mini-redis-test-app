import asyncio
import unittest

from internal.arena.events.history import EventHistory
from internal.arena.gateway.models import MessageResponse, ScenarioRunInput
from internal.arena.scenario.runner import ArenaScenarioRunner


class _FakeGatewayService:
    def __init__(self) -> None:
        self.seed_calls: list[dict[str, str]] = []
        self.execute_calls: list[object] = []
        self.messages: list[tuple[str, str]] = []
        self.reset_calls = 0

    async def publish_message(self, event_type: str, message: str) -> MessageResponse:
        self.messages.append((event_type, message))
        return MessageResponse(message=message)

    async def reset_state(self) -> None:
        self.reset_calls += 1

    async def seed_state(
        self,
        documents: dict[str, str],
        *,
        warm_cache: bool = False,
        ttl_enabled: bool = False,
        ttl_seconds: float | None = None,
    ) -> None:
        self.seed_calls.append(documents)

    async def execute_scenario_command(self, command_input) -> None:
        self.execute_calls.append(command_input)
        await asyncio.sleep(0.01)


class ScenarioRunnerStatusTests(unittest.IsolatedAsyncioTestCase):
    async def test_status_tracks_active_label_during_run(self) -> None:
        gateway_service = _FakeGatewayService()
        runner = ArenaScenarioRunner(
            gateway_service=gateway_service,
            event_history=EventHistory(),
        )

        response = await runner.run(
            ScenarioRunInput(
                scenario_id="read",
                users=1,
                duration_seconds=1,
                read_hot_percent=40,
                ttl_enabled=True,
                ttl_seconds=2.0,
            )
        )

        self.assertEqual(response.message, "Scenario accepted: read 40%")
        self.assertTrue(runner.status()["running"])
        self.assertEqual(runner.status()["active_label"], "read 40%")

        await asyncio.sleep(0.2)

        self.assertFalse(runner.status()["running"])
        self.assertIsNone(runner.status()["active_label"])
        self.assertEqual(gateway_service.messages[-1], ("scenario_finished", "Scenario finished: read 40%"))


if __name__ == "__main__":
    unittest.main()

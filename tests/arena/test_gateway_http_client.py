import unittest

from internal.arena.common.models import ArenaRequest
from internal.arena.gateway.lane_client import ArenaLaneClientSettings
from internal.arena.gateway.lane_client import ArenaLaneHttpClient


class StubArenaLaneHttpClient(ArenaLaneHttpClient):
    def _post_json(self, path, payload):
        if path == "/execute":
            return {
                "request_id": payload["request_id"],
                "lane": "redis_db",
                "status": "ok",
                "latency_ms": 4.8,
                "value_preview": payload.get("value"),
                "path": ["redis_read"],
                "storage_changes": ["Redis value returned"],
                "cache": {"hit": True, "miss": False},
                "mongo_reads": 0,
                "metrics": {
                    "service_time_ms": 1.1,
                    "db_time_ms": 0.2,
                    "redis_time_ms": 0.6,
                    "started_at_ns": 1,
                    "finished_at_ns": 2,
                },
            }
        return {"message": "ok"}

    def _get_json(self, path):
        return {"status": "ok", "lane": "stub"}


class ArenaLaneHttpClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_execute_parses_lane_metrics_and_health(self) -> None:
        client = StubArenaLaneHttpClient(
            settings=ArenaLaneClientSettings(name="stub-lane", base_url="http://stub")
        )

        result = await client.execute(
            ArenaRequest(
                request_id="req-http",
                mode="manual",
                command="GET",
                key="user:1",
                ttl_enabled=False,
            )
        )

        self.assertEqual(result.metrics.service_time_ms, 1.1)
        self.assertIsNotNone(result.metrics.gateway_round_trip_ms)

        health = await client.health()
        self.assertEqual(health["status"], "ok")

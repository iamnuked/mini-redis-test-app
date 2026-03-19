import unittest

from internal.arena.events.bus import ArenaEventBus
from internal.arena.events.history import EventHistory
from internal.arena.gateway.models import CacheResult, LaneResult, ManualCommandInput
from internal.arena.gateway.result_normalizer import build_summary
from internal.arena.gateway.service import ArenaGatewayService
from internal.arena.lane.db_only_adapter import DBOnlyLaneAdapter
from internal.arena.lane.redis_client import InMemoryMiniRedisClient
from internal.arena.lane.redis_db_adapter import RedisDBLaneAdapter
from internal.arena.mongo.repository import InMemoryMongoRepository


class SummaryTests(unittest.TestCase):
    def test_build_summary_picks_lower_latency_and_mongo_reads(self) -> None:
        redis_result = LaneResult(
            request_id="req-summary",
            lane="redis_db",
            status="ok",
            latency_ms=1.2,
            value_preview="v",
            path=["redis_read"],
            storage_changes=["Redis value returned"],
            cache=CacheResult(hit=True),
            mongo_reads=0,
        )
        db_only_result = LaneResult(
            request_id="req-summary",
            lane="db_only",
            status="ok",
            latency_ms=4.8,
            value_preview="v",
            path=["mongo_read"],
            storage_changes=["Mongo document read"],
            cache=CacheResult(),
            mongo_reads=1,
        )

        summary = build_summary(redis_result, db_only_result)

        self.assertEqual(summary.faster_lane, "redis_db")
        self.assertEqual(summary.fewer_mongo_reads_lane, "redis_db")
        self.assertEqual(summary.mongo_read_gap, 1)


class GatewayResetTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.redis_client = InMemoryMiniRedisClient()
        self.redis_repo = InMemoryMongoRepository(name="lane_a")
        self.db_only_repo = InMemoryMongoRepository(name="lane_b")
        self.service = ArenaGatewayService(
            redis_lane=RedisDBLaneAdapter(
                redis_client=self.redis_client,
                repository=self.redis_repo,
            ),
            db_only_lane=DBOnlyLaneAdapter(repository=self.db_only_repo),
            event_bus=ArenaEventBus(),
            event_history=EventHistory(),
        )

    async def test_initialize_applies_default_memory_profile_without_locking(self) -> None:
        await self.service.initialize()

        self.assertEqual(self.redis_client.info_memory()["maxmemory"], 512)
        self.assertFalse(self.service._memory_locked)

    async def test_reset_state_deletes_known_keys_only(self) -> None:
        await self.service.execute_manual_command(
            ManualCommandInput(
                command="SET",
                key="user:10",
                value='{"name":"han"}',
                ttl_enabled=True,
            )
        )

        self.assertEqual(self.redis_client.get("user:10"), '{"name":"han"}')
        self.assertEqual(self.db_only_repo.read("user:10"), '{"name":"han"}')

        await self.service.reset_state()

        self.assertIsNone(self.redis_client.get("user:10"))
        self.assertIsNone(self.db_only_repo.read("user:10"))


if __name__ == "__main__":
    unittest.main()

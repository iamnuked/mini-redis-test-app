import unittest

from internal.arena.gateway.models import ArenaRequest
from internal.arena.lane.redis_client import InMemoryMiniRedisClient
from internal.arena.lane.redis_db_adapter import RedisDBLaneAdapter
from internal.arena.mongo.repository import InMemoryMongoRepository


class RedisDBLaneAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.redis_client = InMemoryMiniRedisClient()
        self.repository = InMemoryMongoRepository(name="lane_a")
        self.adapter = RedisDBLaneAdapter(
            redis_client=self.redis_client,
            repository=self.repository,
        )

    async def test_set_then_get_hits_cache(self) -> None:
        await self.adapter.execute(
            ArenaRequest(
                request_id="req-set",
                mode="manual",
                command="SET",
                key="user:1",
                value='{"name":"kim"}',
                ttl_enabled=False,
            )
        )

        result = await self.adapter.execute(
            ArenaRequest(
                request_id="req-get",
                mode="manual",
                command="GET",
                key="user:1",
                ttl_enabled=False,
            )
        )

        self.assertTrue(result.cache.hit)
        self.assertEqual(result.mongo_reads, 0)
        self.assertIn("redis_hit", result.path)

    async def test_miss_reads_mongo_and_backfills_redis(self) -> None:
        self.repository.write("user:2", '{"name":"lee"}')

        result = await self.adapter.execute(
            ArenaRequest(
                request_id="req-miss",
                mode="manual",
                command="GET",
                key="user:2",
                ttl_enabled=True,
            )
        )

        self.assertTrue(result.cache.miss)
        self.assertEqual(result.mongo_reads, 1)
        self.assertIn("redis_fill", result.path)
        self.assertIn("redis_expire", result.path)
        self.assertEqual(self.redis_client.get("user:2"), '{"name":"lee"}')


if __name__ == "__main__":
    unittest.main()

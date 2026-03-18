import time
import unittest

from internal.arena.lane.redis_client import InMemoryMiniRedisClient


class InMemoryMiniRedisClientTests(unittest.TestCase):
    def test_expire_and_ttl(self) -> None:
        client = InMemoryMiniRedisClient()
        client.set("session:1", "warm")

        self.assertTrue(client.expire("session:1", 1))
        self.assertIsNotNone(client.ttl("session:1"))

        time.sleep(1.05)

        self.assertIsNone(client.get("session:1"))
        self.assertIsNone(client.ttl("session:1"))


if __name__ == "__main__":
    unittest.main()

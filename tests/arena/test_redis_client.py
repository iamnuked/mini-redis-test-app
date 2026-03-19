import time
import unittest

from internal.arena.lane.redis_client import InMemoryMiniRedisClient
from internal.arena.lane.redis_client import MiniRedisConnectionSettings
from internal.arena.lane.redis_client import RedisPyMiniRedisClient


class InMemoryMiniRedisClientTests(unittest.TestCase):
    def test_expire_and_ttl(self) -> None:
        client = InMemoryMiniRedisClient()
        client.set("session:1", "warm")

        self.assertTrue(client.expire("session:1", 1))
        self.assertIsNotNone(client.ttl("session:1"))

        time.sleep(1.05)

        self.assertIsNone(client.get("session:1"))
        self.assertIsNone(client.ttl("session:1"))


class _FakePool:
    def __init__(self) -> None:
        self.disconnect_calls = 0

    def disconnect(self) -> None:
        self.disconnect_calls += 1


class _FakeRedisConnection:
    def __init__(self) -> None:
        self.connection_pool = _FakePool()
        self.closed = 0
        self._strings: dict[str, str] = {}
        self._hashes: dict[str, dict[str, str]] = {}
        self._maxmemory = 0

    def close(self) -> None:
        self.closed += 1

    def set(self, *, name: str, value: str) -> None:
        self._strings[name] = value

    def get(self, *, name: str) -> str | None:
        return self._strings.get(name)

    def hset(self, *, name: str, key: str, value: str) -> None:
        self._hashes.setdefault(name, {})[key] = value

    def hget(self, *, name: str, key: str) -> str | None:
        return self._hashes.get(name, {}).get(key)

    def hgetall(self, *, name: str) -> dict[str, str]:
        return dict(self._hashes.get(name, {}))

    def delete(self, key: str) -> int:
        deleted = 0
        if key in self._strings:
            del self._strings[key]
            deleted += 1
        if key in self._hashes:
            del self._hashes[key]
            deleted += 1
        return deleted

    def expire(self, key: str, ttl_seconds: float) -> int:
        return 1 if key in self._strings or key in self._hashes else 0

    def ttl(self, key: str) -> int:
        return -1

    def ping(self) -> bool:
        return True

    def execute_command(self, *arguments):
        if arguments == ("FLUSHDB",):
            self._strings.clear()
            self._hashes.clear()
            return "OK"
        if arguments[:1] == ("EXPIRE",):
            key = arguments[1]
            return 1 if key in self._strings or key in self._hashes else 0
        if arguments == ("DBSIZE",):
            return len(set(self._strings) | set(self._hashes))
        if arguments == ("INFO", "MEMORY"):
            keys = len(set(self._strings) | set(self._hashes))
            return {
                "used_memory": 0,
                "maxmemory": self._maxmemory,
                "keys": keys,
                "evicted_keys": 0,
            }
        if arguments[:3] == ("CONFIG", "SET", "maxmemory"):
            self._maxmemory = int(arguments[3])
            return "OK"
        if arguments[:3] == ("CONFIG", "GET", "maxmemory"):
            return ["maxmemory", str(self._maxmemory)]
        raise AssertionError(f"Unexpected command: {arguments!r}")


class _FakeRedisModule:
    def __init__(self) -> None:
        self.instances: list[_FakeRedisConnection] = []

    def Redis(self, **_: object) -> _FakeRedisConnection:
        connection = _FakeRedisConnection()
        self.instances.append(connection)
        return connection


class _TestRedisPyMiniRedisClient(RedisPyMiniRedisClient):
    def __init__(
        self,
        *,
        settings: MiniRedisConnectionSettings,
        redis_module: _FakeRedisModule,
    ) -> None:
        self._test_redis_module = redis_module
        super().__init__(settings=settings)

    def _load_redis_module(self):
        return self._test_redis_module


class RedisPyMiniRedisClientTests(unittest.TestCase):
    def test_reuses_single_client_until_closed(self) -> None:
        fake_module = _FakeRedisModule()
        client = _TestRedisPyMiniRedisClient(
            settings=MiniRedisConnectionSettings(backend="redis_py"),
            redis_module=fake_module,
        )

        client.set("user:1", "kim")
        self.assertEqual(client.get("user:1"), "kim")
        client.hset("user:hash:1", "name", "lee")
        self.assertEqual(client.hget("user:hash:1", "name"), "lee")

        self.assertEqual(len(fake_module.instances), 1)

        client.close()

        self.assertEqual(fake_module.instances[0].closed, 1)
        self.assertEqual(fake_module.instances[0].connection_pool.disconnect_calls, 1)

        self.assertTrue(client.ping())
        self.assertEqual(len(fake_module.instances), 2)


if __name__ == "__main__":
    unittest.main()

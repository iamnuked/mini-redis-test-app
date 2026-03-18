from __future__ import annotations

import socket
import sys
import threading
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.adapters.baseline import BaselineClient
from app.adapters.mini_redis import MiniRedisClient
from app.benchmark.models import RunConfig, RunRecord, utc_now_iso
from app.benchmark.runner import BenchmarkRunner
from app.storage.run_store import RunStore


MINI_REDIS_ROOT = Path(".tmp/mini-redis-dev").resolve()
if str(MINI_REDIS_ROOT) not in sys.path:
    sys.path.insert(0, str(MINI_REDIS_ROOT))

from internal.config.runtime_config import RuntimeConfig  # type: ignore  # noqa: E402
from internal.server.server import MiniRedisServer  # type: ignore  # noqa: E402
from internal.server.shutdown import ShutdownManager  # type: ignore  # noqa: E402


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for_server(host: str, port: int, timeout_seconds: float = 5.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.05)
    raise TimeoutError(f"server did not start on {host}:{port}")


class MiniRedisIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        port = find_free_port()
        config = RuntimeConfig.default().with_connection_target(host="127.0.0.1", port=port)
        self._server = MiniRedisServer(config=config, shutdown_manager=ShutdownManager())
        self._thread = threading.Thread(target=self._server.run, daemon=True)
        self._thread.start()
        wait_for_server(config.host, config.port)
        self._client = MiniRedisClient(host=config.host, port=config.port, timeout_seconds=1.0)

    def tearDown(self) -> None:
        self._client.close()
        self._server.stop()
        self._thread.join(timeout=2)

    def test_mini_redis_client_health_and_basic_commands(self) -> None:
        self.assertTrue(self._client.health_check())
        self.assertTrue(self._client.set("benchmark:test:key", "value"))
        self.assertEqual(self._client.get("benchmark:test:key"), "value")
        self.assertEqual(self._client.expire("benchmark:test:key", 5), 1)
        ttl_value = self._client.ttl("benchmark:test:key")
        self.assertGreaterEqual(ttl_value, 0)
        self.assertEqual(self._client.delete("benchmark:test:key"), 1)
        self.assertIsNone(self._client.get("benchmark:test:key"))

    def test_benchmark_runner_completes_against_real_mini_redis(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            store = RunStore(Path(tmp_dir))
            runner = BenchmarkRunner(
                store=store,
                baseline_client=BaselineClient(db_latency_ms=1.0),
                redis_client=self._client,
            )
            now = utc_now_iso()
            record = RunRecord(
                run_id="run_integration",
                status="queued",
                config=RunConfig(
                    scenario="detail_page",
                    iteration_count=2,
                    concurrency=1,
                    hit_rate_buckets=[0, 100],
                    ttl_seconds=5,
                    include_reference=True,
                ),
                created_at=now,
                updated_at=now,
            )
            store.write_run(record)

            runner.run("run_integration")

            loaded = store.read_run("run_integration")
            events = store.read_events("run_integration")

            self.assertEqual(loaded.status, "completed")
            self.assertIsNotNone(loaded.summary)
            self.assertEqual(loaded.summary.redis_hit_count, 2)
            self.assertEqual(loaded.summary.redis_miss_count, 2)
            self.assertGreater(len(events), 0)
            self.assertTrue(any(event["event_type"] == "cache_hit" for event in events))
            self.assertTrue(any(event["event_type"] == "cache_miss" for event in events))
            self.assertTrue(any(event["mode"] == "redis_only_reference" for event in events))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import http.client
import json
import socket
import threading
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.adapters.mini_redis import MiniRedisError
from app.api.config import ControllerSettings
from app.api.server import BenchmarkApplication, create_server
from app.benchmark.models import RunConfig, RunRecord, RunSummary, utc_now_iso
from app.storage.run_store import RunStore


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class ApiServerTest(unittest.TestCase):
    def test_root_serves_frontend_index_html(self) -> None:
        with _ServerHarness(_NoopRunner(), _FakeRedisClient("127.0.0.9", 6380, True)) as harness:
            status, payload, headers = harness.request_text("GET", "/")

        self.assertEqual(status, 200)
        self.assertIn("<title>미니 레디스 벤치마크 랩</title>", payload)
        self.assertIn("text/html", headers["Content-Type"])

    def test_options_request_returns_cors_headers(self) -> None:
        with _ServerHarness(_NoopRunner(), _FakeRedisClient("127.0.0.9", 6380, True)) as harness:
            status, payload, headers = harness.request_text("OPTIONS", "/api/health")

        self.assertEqual(status, 204)
        self.assertEqual(payload, "")
        self.assertEqual(headers["Access-Control-Allow-Origin"], "*")
        self.assertIn("OPTIONS", headers["Access-Control-Allow-Methods"])

    def test_health_endpoint_uses_injected_redis_client(self) -> None:
        with _ServerHarness(_NoopRunner(), _FakeRedisClient("127.0.0.9", 6380, True)) as harness:
            status, payload = harness.request("GET", "/api/health")

        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["host"], "127.0.0.9")
        self.assertEqual(payload["port"], 6380)

    def test_create_run_rejects_invalid_json_body(self) -> None:
        with _ServerHarness(_NoopRunner(), _FakeRedisClient("127.0.0.1", 6379, True)) as harness:
            status, payload = harness.request(
                "POST",
                "/api/benchmark-runs",
                raw_body=b"{oops",
                headers={"Content-Type": "application/json"},
            )

        self.assertEqual(status, 400)
        self.assertEqual(payload["error"], "invalid JSON body")

    def test_create_run_returns_conflict_while_active_run_is_running(self) -> None:
        with _ServerHarness(None, _FakeRedisClient("127.0.0.1", 6379, True)) as harness:
            runner = _BlockingRunner(harness.store)
            harness.set_runner(runner)
            status1, payload1 = harness.request(
                "POST",
                "/api/benchmark-runs",
                body={"scenario": "detail_page", "iteration_count": 1},
            )
            self.assertEqual(status1, 201)
            self.assertTrue(runner.started.wait(timeout=2))

            status2, payload2 = harness.request(
                "POST",
                "/api/benchmark-runs",
                body={"scenario": "detail_page", "iteration_count": 1},
            )
            self.assertEqual(status2, 409)
            self.assertEqual(payload2["error"], "another benchmark run is already active")

            runner.release.set()
            self.assertTrue(runner.finished.wait(timeout=2))

            status3, payload3 = harness.request("GET", f"/api/benchmark-runs/{payload1['run_id']}")

        self.assertEqual(status3, 200)
        self.assertEqual(payload3["status"], "completed")

    def test_events_endpoint_rejects_invalid_after_value(self) -> None:
        with _ServerHarness(_NoopRunner(), _FakeRedisClient("127.0.0.1", 6379, True)) as harness:
            status, payload = harness.request("GET", "/api/benchmark-runs/run_missing/events?after=nope")

        self.assertEqual(status, 400)
        self.assertEqual(payload["error"], "invalid after query parameter")

    def test_run_detail_response_contains_documented_keys(self) -> None:
        with _ServerHarness(_NoopRunner(), _FakeRedisClient("127.0.0.1", 6379, True)) as harness:
            now = utc_now_iso()
            harness.store.write_run(
                RunRecord(
                    run_id="run_doc_shape",
                    status="completed",
                    config=RunConfig("detail_page", 10, 1, [0, 50, 100], 30, True),
                    created_at=now,
                    updated_at=now,
                    started_at=now,
                    finished_at=now,
                    summary=RunSummary(
                        db_avg_ms=100.0,
                        redis_avg_ms=25.0,
                        reference_avg_ms=10.0,
                        p95_db_ms=120.0,
                        p95_redis_ms=30.0,
                        p95_reference_ms=12.0,
                        speedup_ratio=4.0,
                        improvement_percent=75.0,
                        break_even_hit_rate=50,
                        cache_hit_rate=60.0,
                        db_only_count=10,
                        redis_hit_count=6,
                        redis_miss_count=4,
                        fallback_count=1,
                        error_count=1,
                    ),
                )
            )
            harness.store.append_log("run_doc_shape", "INFO", "aggregation", "done")

            status, payload = harness.request("GET", "/api/benchmark-runs/run_doc_shape")

        self.assertEqual(status, 200)
        self.assertEqual(
            set(payload.keys()),
            {
                "run_id",
                "status",
                "config",
                "created_at",
                "updated_at",
                "started_at",
                "finished_at",
                "summary",
                "error_message",
                "mini_redis_commit",
                "app_commit",
                "logs",
            },
        )
        self.assertEqual(payload["logs"][0]["metadata"], {})
        self.assertIn("reference_avg_ms", payload["summary"])

    def test_events_endpoint_returns_normalized_event_shape(self) -> None:
        with _ServerHarness(_NoopRunner(), _FakeRedisClient("127.0.0.1", 6379, True)) as harness:
            now = utc_now_iso()
            harness.store.write_run(
                RunRecord(
                    run_id="run_events_shape",
                    status="completed",
                    config=RunConfig("detail_page", 1, 1, [0], 30),
                    created_at=now,
                    updated_at=now,
                )
            )
            harness.store.append_event(
                "run_events_shape",
                _FakeEvent(
                    {
                        "event_id": "evt_1",
                        "request_id": "req_1",
                        "timestamp": 1,
                        "mode": "db_only",
                        "event_type": "response_sent",
                        "stage": "response",
                        "duration_ms": 0,
                    }
                ),
            )

            status, payload = harness.request("GET", "/api/benchmark-runs/run_events_shape/events")

        self.assertEqual(status, 200)
        self.assertEqual(payload["run_id"], "run_events_shape")
        self.assertEqual(payload["events"][0]["metadata"], {})
        self.assertIsInstance(payload["events"][0]["timestamp"], float)

    def test_requests_endpoint_returns_request_timelines(self) -> None:
        with _ServerHarness(_NoopRunner(), _FakeRedisClient("127.0.0.1", 6379, True)) as harness:
            now = utc_now_iso()
            harness.store.write_run(
                RunRecord(
                    run_id="run_requests_shape",
                    status="completed",
                    config=RunConfig("detail_page", 1, 1, [50], 30),
                    created_at=now,
                    updated_at=now,
                )
            )
            harness.store.append_event(
                "run_requests_shape",
                _FakeEvent(
                    {
                        "event_id": "cache-1-start",
                        "request_id": "cache-1",
                        "timestamp": 0,
                        "mode": "cache_aside",
                        "event_type": "request_started",
                        "stage": "request",
                        "duration_ms": 0,
                    }
                ),
            )
            harness.store.append_event(
                "run_requests_shape",
                _FakeEvent(
                    {
                        "event_id": "cache-1-response",
                        "request_id": "cache-1",
                        "timestamp": 21.2,
                        "mode": "cache_aside",
                        "event_type": "response_sent",
                        "stage": "response",
                        "duration_ms": 0,
                        "metadata": {"total_duration_ms": 21.2, "cache_status": "miss"},
                    }
                ),
            )

            status, payload = harness.request("GET", "/api/benchmark-runs/run_requests_shape/requests")

        self.assertEqual(status, 200)
        self.assertEqual(payload["run_id"], "run_requests_shape")
        self.assertEqual(payload["requests"][0]["request_id"], "cache-1")
        self.assertEqual(payload["requests"][0]["cache_status"], "miss")
        self.assertEqual(payload["requests"][0]["path_summary"], "App -> Redis -> DB -> Redis -> Response")

    def test_presentation_endpoint_returns_dashboard_read_model(self) -> None:
        with _ServerHarness(_NoopRunner(), _FakeRedisClient("127.0.0.1", 6379, True)) as harness:
            now = utc_now_iso()
            harness.store.write_run(
                RunRecord(
                    run_id="run_presentation",
                    status="completed",
                    config=RunConfig("detail_page", 2, 1, [0, 100], 30, True),
                    created_at=now,
                    updated_at=now,
                    summary=RunSummary(
                        db_avg_ms=100.0,
                        redis_avg_ms=25.0,
                        reference_avg_ms=10.0,
                        p95_db_ms=120.0,
                        p95_redis_ms=30.0,
                        p95_reference_ms=12.0,
                        speedup_ratio=4.0,
                        improvement_percent=75.0,
                        break_even_hit_rate=50,
                        cache_hit_rate=60.0,
                        db_only_count=2,
                        redis_hit_count=2,
                        redis_miss_count=2,
                        fallback_count=0,
                        error_count=0,
                    ),
                )
            )
            harness.store.append_event(
                "run_presentation",
                _FakeEvent(
                    {
                        "event_id": "baseline-0-response",
                        "request_id": "baseline-0",
                        "timestamp": 18,
                        "mode": "db_only",
                        "event_type": "response_sent",
                        "stage": "response",
                        "duration_ms": 0,
                        "metadata": {"total_duration_ms": 18},
                    }
                ),
            )
            harness.store.append_event(
                "run_presentation",
                _FakeEvent(
                    {
                        "event_id": "cache-0-response",
                        "request_id": "cache-0",
                        "timestamp": 21,
                        "mode": "cache_aside",
                        "event_type": "response_sent",
                        "stage": "response",
                        "duration_ms": 0,
                        "metadata": {"total_duration_ms": 21, "cache_status": "miss"},
                    }
                ),
            )

            status, payload = harness.request("GET", "/api/benchmark-runs/run_presentation/presentation")

        self.assertEqual(status, 200)
        self.assertEqual(payload["run_id"], "run_presentation")
        self.assertEqual(payload["kpis"]["db_avg_ms"], 100.0)
        self.assertIn("redis_hit_avg_ms", payload["kpis"])
        self.assertIn("redis_miss_avg_ms", payload["kpis"])
        self.assertIn("lane_summary", payload)
        self.assertIn("chart_series", payload)
        self.assertEqual(payload["chart_series"]["latency_comparison"][0]["label"], "DB Only Avg")


class _ServerHarness:
    def __init__(self, runner: object | None, redis_client: object) -> None:
        self._runner = runner or _NoopRunner()
        self._redis_client = redis_client
        self._tmp_dir = TemporaryDirectory()
        self._store = RunStore(Path(self._tmp_dir.name))
        self._server = None
        self._thread = None

    def __enter__(self) -> "_ServerHarness":
        app = BenchmarkApplication(
            store=self._store,
            runner=self._runner,  # type: ignore[arg-type]
            redis_client=self._redis_client,  # type: ignore[arg-type]
        )
        settings = ControllerSettings(controller_host="127.0.0.1", controller_port=find_free_port())
        self._server = create_server(settings=settings, app=app)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        self._wait_for_server(settings.controller_host, settings.controller_port)
        self._host = settings.controller_host
        self._port = settings.controller_port
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        assert self._server is not None
        assert self._thread is not None
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2)
        self._tmp_dir.cleanup()

    @property
    def store(self) -> RunStore:
        return self._store

    def set_runner(self, runner: object) -> None:
        self._runner = runner
        assert self._server is not None
        self._server.app.runner = runner  # type: ignore[assignment]

    def request(
        self,
        method: str,
        path: str,
        body: dict | None = None,
        raw_body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict]:
        payload = raw_body
        request_headers = {"Accept": "application/json"}
        if headers:
            request_headers.update(headers)
        if body is not None:
            payload = json.dumps(body).encode()
            request_headers.setdefault("Content-Type", "application/json")
        conn = http.client.HTTPConnection(self._host, self._port, timeout=2)
        try:
            conn.request(method, path, body=payload, headers=request_headers)
            response = conn.getresponse()
            data = response.read()
            return response.status, json.loads(data.decode() or "{}")
        finally:
            conn.close()

    def request_text(
        self,
        method: str,
        path: str,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, str, dict[str, str]]:
        conn = http.client.HTTPConnection(self._host, self._port, timeout=2)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            response = conn.getresponse()
            data = response.read().decode()
            header_map = {key: value for key, value in response.getheaders()}
            return response.status, data, header_map
        finally:
            conn.close()

    @staticmethod
    def _wait_for_server(host: str, port: int, timeout_seconds: float = 5.0) -> None:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            try:
                with socket.create_connection((host, port), timeout=0.2):
                    return
            except OSError:
                time.sleep(0.05)
        raise TimeoutError(f"server did not start on {host}:{port}")


class _FakeRedisClient:
    def __init__(self, host: str, port: int, ok: bool) -> None:
        self._host = host
        self._port = port
        self._ok = ok

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    def health_check(self) -> bool:
        if self._ok:
            return True
        raise MiniRedisError("health failed")


class _NoopRunner:
    def run(self, run_id: str) -> None:
        return


class _BlockingRunner:
    def __init__(self, store: RunStore) -> None:
        self._store = store
        self.started = threading.Event()
        self.release = threading.Event()
        self.finished = threading.Event()

    def run(self, run_id: str) -> None:
        self.started.set()
        self.release.wait(timeout=2)
        record = self._store.read_run(run_id)
        record.status = "completed"
        record.updated_at = utc_now_iso()
        record.finished_at = utc_now_iso()
        self._store.write_run(record)
        self.finished.set()


class _FakeEvent:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def to_dict(self) -> dict:
        return dict(self._payload)


if __name__ == "__main__":
    unittest.main()

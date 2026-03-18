from __future__ import annotations

import json
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from json import JSONDecodeError
from pathlib import Path
from mimetypes import guess_type
from typing import Any
from urllib.parse import parse_qs, urlparse

from app.adapters.baseline import BaselineClient
from app.adapters.mini_redis import MiniRedisClient, MiniRedisError
from app.adapters.mongodb_baseline import MongoBaselineClient, MongoBaselineError
from app.api.config import ControllerSettings
from app.api.contracts import (
    serialize_events_response,
    serialize_presentation_response,
    serialize_requests_response,
    serialize_run_detail,
)
from app.api.presentation import build_presentation_payload
from app.api.scenarios import DEFAULT_HIT_RATE_BUCKETS, default_demo_config, get_scenario, list_scenarios
from app.api.timeline import build_request_timelines
from app.benchmark.models import RunConfig, RunRecord, utc_now_iso
from app.benchmark.runner import BenchmarkRunner
from app.storage.run_store import RunStore, build_run_id

STATIC_ROOT = Path(__file__).resolve().parents[1] / "ui" / "static"


class BenchmarkApplication:
    def __init__(
        self,
        store: RunStore,
        runner: BenchmarkRunner,
        redis_client: MiniRedisClient,
        baseline_client: BaselineClient,
    ) -> None:
        self.store = store
        self.runner = runner
        self.redis_client = redis_client
        self.baseline_client = baseline_client
        self._run_lock = threading.Lock()
        self._active_run_id: str | None = None
        self._cancel_events: dict[str, threading.Event] = {}

    def create_run(self, config: RunConfig) -> RunRecord | None:
        run_id = build_run_id()
        now = utc_now_iso()
        record = RunRecord(
            run_id=run_id,
            status="queued",
            config=config,
            created_at=now,
            updated_at=now,
        )
        with self._run_lock:
            if self._active_run_id is not None or self.store.has_active_run():
                return None
            self._active_run_id = run_id
            self._cancel_events[run_id] = threading.Event()
            self.store.write_run(record)
            self.store.append_log(run_id, "INFO", "bootstrap", "benchmark queued")
            threading.Thread(target=self._run_and_release, args=(run_id,), daemon=True).start()
            return record

    def stop_run(self, run_id: str) -> tuple[bool, str]:
        with self._run_lock:
            cancel_event = self._cancel_events.get(run_id)
            if self._active_run_id != run_id or cancel_event is None:
                return False, "run is not active"
            if cancel_event.is_set():
                return False, "run is already cancelling"
            cancel_event.set()

        record = self.store.read_run(run_id)
        if record.status not in {"cancelled", "completed", "failed"}:
            record.status = "cancelling"
            record.updated_at = utc_now_iso()
            self.store.write_run(record)
            self.store.append_log(run_id, "INFO", "cancel", "benchmark cancellation requested")
        return True, "cancellation requested"

    def _run_and_release(self, run_id: str) -> None:
        try:
            self.runner.run(run_id, cancel_event=self._cancel_events.get(run_id))
        finally:
            with self._run_lock:
                if self._active_run_id == run_id:
                    self._active_run_id = None
                self._cancel_events.pop(run_id, None)


class BenchmarkHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], app: BenchmarkApplication) -> None:
        self.app = app
        super().__init__(server_address, BenchmarkRequestHandler)


class BenchmarkRequestHandler(BaseHTTPRequestHandler):
    server_version = "MiniRedisBenchmarkHTTP/0.2"

    @property
    def app(self) -> BenchmarkApplication:
        return self.server.app  # type: ignore[attr-defined]

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in {"", "/"}:
            self._serve_static("index.html")
            return

        if parsed.path == "/api/health":
            self._handle_health()
            return

        if parsed.path == "/api/benchmark-runs":
            self._handle_run_list()
            return

        if parsed.path == "/api/scenarios":
            self._write_json({"scenarios": list_scenarios()})
            return

        if parsed.path.startswith("/api/scenarios/"):
            parts = parsed.path.strip("/").split("/")
            if len(parts) < 3:
                self._write_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
                return
            scenario = get_scenario(parts[2])
            if scenario is None:
                self._write_json({"error": "scenario not found"}, HTTPStatus.NOT_FOUND)
                return
            self._write_json(scenario)
            return

        if parsed.path == "/api/demo-config":
            self._write_json(default_demo_config())
            return

        if parsed.path.startswith("/api/benchmark-runs/") and parsed.path.endswith("/events"):
            parts = parsed.path.strip("/").split("/")
            if len(parts) < 4:
                self._write_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
                return
            run_id = parts[2]
            self._handle_events(run_id, parse_qs(parsed.query))
            return

        if parsed.path.startswith("/api/benchmark-runs/") and parsed.path.endswith("/presentation"):
            parts = parsed.path.strip("/").split("/")
            if len(parts) < 4:
                self._write_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
                return
            run_id = parts[2]
            self._handle_presentation(run_id)
            return

        if parsed.path.startswith("/api/benchmark-runs/") and parsed.path.endswith("/requests"):
            parts = parsed.path.strip("/").split("/")
            if len(parts) < 4:
                self._write_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
                return
            run_id = parts[2]
            self._handle_request_timelines(run_id)
            return

        if parsed.path.startswith("/api/benchmark-runs/"):
            parts = parsed.path.strip("/").split("/")
            if len(parts) < 3:
                self._write_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
                return
            run_id = parts[2]
            self._handle_run_status(run_id)
            return

        if self._try_serve_static_path(parsed.path):
            return

        self._write_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/benchmark-runs":
            self._handle_create_run()
            return

        if parsed.path.startswith("/api/benchmark-runs/") and parsed.path.endswith("/stop"):
            parts = parsed.path.strip("/").split("/")
            if len(parts) < 4:
                self._write_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
                return
            run_id = parts[2]
            self._handle_stop_run(run_id)
            return

        if parsed.path == "/api/demo-actions/seed-data":
            self._handle_seed_data()
            return

        if parsed.path == "/api/demo-actions/clear-redis":
            self._handle_clear_redis()
            return

        self._write_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT.value)
        self._write_common_headers()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _handle_health(self) -> None:
        client = self.app.redis_client
        try:
            ok = client.health_check()
        except MiniRedisError as exc:
            self._write_json(
                {
                    "status": "down",
                    "host": client.host,
                    "port": client.port,
                    "error": str(exc),
                },
                HTTPStatus.SERVICE_UNAVAILABLE,
            )
            return

        self._write_json(
            {
                "status": "ok" if ok else "down",
                "host": client.host,
                "port": client.port,
            }
        )

    def _handle_create_run(self) -> None:
        try:
            body = self._read_json_body()
        except ValueError as exc:
            self._write_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        try:
            config = _build_run_config(body)
        except ValueError as exc:
            self._write_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        record = self.app.create_run(config)
        if record is None:
            self._write_json(
                {"error": "another benchmark run is already active"},
                HTTPStatus.CONFLICT,
            )
            return

        self._write_json(
            {
                "run_id": record.run_id,
                "status": record.status,
                "scenario": record.config.scenario,
                "created_at": record.created_at,
            },
            HTTPStatus.CREATED,
        )

    def _handle_run_status(self, run_id: str) -> None:
        try:
            record = self.app.store.read_run(run_id)
        except FileNotFoundError:
            self._write_json({"error": "run not found"}, HTTPStatus.NOT_FOUND)
            return
        payload = serialize_run_detail(record, self.app.store.read_logs(run_id))
        self._write_json(payload)

    def _handle_stop_run(self, run_id: str) -> None:
        try:
            self.app.store.read_run(run_id)
        except FileNotFoundError:
            self._write_json({"error": "run not found"}, HTTPStatus.NOT_FOUND)
            return

        stopped, message = self.app.stop_run(run_id)
        if not stopped:
            self._write_json({"error": message}, HTTPStatus.CONFLICT)
            return
        self._write_json({"run_id": run_id, "status": "cancelling", "message": message})

    def _handle_seed_data(self) -> None:
        baseline_client = self.app.baseline_client
        seed_method = getattr(baseline_client, "seed", None)
        if not callable(seed_method):
            self._write_json(
                {"error": "seed-data is only available when using the mongodb baseline backend"},
                HTTPStatus.BAD_REQUEST,
            )
            return

        try:
            inserted = int(seed_method())
        except (MongoBaselineError, RuntimeError, ValueError) as exc:
            self._write_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        collection_name = getattr(baseline_client, "collection_name", "unknown")
        self._write_json(
            {
                "status": "ok",
                "action": "seed-data",
                "inserted": inserted,
                "collection": collection_name,
            }
        )

    def _handle_clear_redis(self) -> None:
        try:
            body = self._read_json_body()
        except ValueError as exc:
            self._write_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        iteration_count = max(1, int(body.get("iteration_count", 10)))
        raw_buckets = body.get("hit_rate_buckets", DEFAULT_HIT_RATE_BUCKETS)
        if not isinstance(raw_buckets, list):
            self._write_json({"error": "hit_rate_buckets must be a JSON array"}, HTTPStatus.BAD_REQUEST)
            return
        try:
            hit_rate_buckets = [int(value) for value in raw_buckets]
        except (TypeError, ValueError):
            self._write_json({"error": "hit_rate_buckets must contain integers"}, HTTPStatus.BAD_REQUEST)
            return

        candidate_keys = _collect_benchmark_keys(self.app.store, iteration_count, hit_rate_buckets)
        removed = 0
        errors: list[str] = []
        for key in candidate_keys:
            try:
                removed += int(self.app.redis_client.delete(key))
            except MiniRedisError as exc:
                errors.append(str(exc))
                break

        status = HTTPStatus.OK if not errors else HTTPStatus.BAD_GATEWAY
        self._write_json(
            {
                "status": "ok" if not errors else "partial",
                "action": "clear-redis",
                "candidate_key_count": len(candidate_keys),
                "removed": removed,
                "error": errors[0] if errors else None,
            },
            status,
        )

    def _handle_events(self, run_id: str, query: dict[str, list[str]]) -> None:
        after_values = query.get("after", [])
        try:
            after = float(after_values[0]) if after_values else None
        except ValueError:
            self._write_json({"error": "invalid after query parameter"}, HTTPStatus.BAD_REQUEST)
            return

        events = self.app.store.read_events_after(run_id, after)
        self._write_json(serialize_events_response(run_id, events))

    def _handle_run_list(self) -> None:
        self._write_json({"runs": self.app.store.list_runs()})

    def _handle_request_timelines(self, run_id: str) -> None:
        events = self.app.store.read_events(run_id)
        self._write_json(serialize_requests_response(run_id, build_request_timelines(events)))

    def _handle_presentation(self, run_id: str) -> None:
        try:
            record = self.app.store.read_run(run_id)
        except FileNotFoundError:
            self._write_json({"error": "run not found"}, HTTPStatus.NOT_FOUND)
            return
        events = self.app.store.read_events(run_id)
        self._write_json(serialize_presentation_response(build_presentation_payload(record, events)))

    def _read_json_body(self) -> dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0:
            return {}
        raw = self.rfile.read(content_length)
        if not raw:
            return {}
        try:
            decoded = json.loads(raw.decode())
        except JSONDecodeError as exc:
            raise ValueError("invalid JSON body") from exc
        if decoded is None:
            return {}
        if not isinstance(decoded, dict):
            raise ValueError("JSON body must be an object")
        return decoded

    def _try_serve_static_path(self, path: str) -> bool:
        if not path.startswith("/"):
            return False
        candidate = path.lstrip("/")
        if not candidate or candidate.startswith("api/"):
            return False
        return self._serve_static(candidate)

    def _serve_static(self, relative_path: str) -> bool:
        candidate = (STATIC_ROOT / relative_path).resolve()
        if STATIC_ROOT not in candidate.parents and candidate != STATIC_ROOT:
            self._write_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return True
        if not candidate.is_file():
            return False

        body = candidate.read_bytes()
        content_type = guess_type(str(candidate))[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK.value)
        self._write_common_headers()
        self.send_header("Content-Type", f"{content_type}; charset=utf-8" if content_type.startswith("text/") or content_type == "application/javascript" else content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        return True

    def _write_common_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _write_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=True).encode()
        self.send_response(status.value)
        self._write_common_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def build_application(
    settings: ControllerSettings | None = None,
    store: RunStore | None = None,
    baseline_client: BaselineClient | None = None,
    redis_client: MiniRedisClient | None = None,
    runner: BenchmarkRunner | None = None,
) -> BenchmarkApplication:
    settings = settings or ControllerSettings.from_env()
    store = store or RunStore()
    baseline_client = baseline_client or _build_baseline_client(settings)
    redis_client = redis_client or MiniRedisClient(
        host=settings.redis_host,
        port=settings.redis_port,
        timeout_seconds=settings.redis_timeout_seconds,
    )
    runner = runner or BenchmarkRunner(store, baseline_client, redis_client)
    return BenchmarkApplication(store=store, runner=runner, redis_client=redis_client, baseline_client=baseline_client)


def create_server(
    settings: ControllerSettings | None = None,
    app: BenchmarkApplication | None = None,
) -> BenchmarkHTTPServer:
    settings = settings or ControllerSettings.from_env()
    app = app or build_application(settings=settings)
    return BenchmarkHTTPServer((settings.controller_host, settings.controller_port), app)


def serve(host: str | None = None, port: int | None = None) -> None:
    settings = ControllerSettings.from_env()
    if host is not None or port is not None:
        settings = ControllerSettings(
            controller_host=host or settings.controller_host,
            controller_port=port or settings.controller_port,
            redis_host=settings.redis_host,
            redis_port=settings.redis_port,
            redis_timeout_seconds=settings.redis_timeout_seconds,
            baseline_backend=settings.baseline_backend,
            mongodb_uri=settings.mongodb_uri,
            mongodb_db_name=settings.mongodb_db_name,
            mongodb_collection=settings.mongodb_collection,
            mongodb_seed_file=settings.mongodb_seed_file,
            mongodb_connect_timeout_ms=settings.mongodb_connect_timeout_ms,
        )
    server = create_server(settings=settings)
    print(f"benchmark controller listening on http://{settings.controller_host}:{settings.controller_port}")
    server.serve_forever()

def _build_run_config(body: dict[str, Any]) -> RunConfig:
    scenario = body.get("scenario", "detail_page")
    iteration_count = int(body.get("iteration_count", 10))
    concurrency = int(body.get("concurrency", 1))
    hit_rate_buckets = [int(value) for value in body.get("hit_rate_buckets", DEFAULT_HIT_RATE_BUCKETS)]
    ttl_seconds = int(body.get("ttl_seconds", 30))
    include_reference = bool(body.get("include_reference", False))

    if iteration_count <= 0:
        raise ValueError("iteration_count must be greater than 0")
    if concurrency <= 0:
        raise ValueError("concurrency must be greater than 0")
    if ttl_seconds <= 0:
        raise ValueError("ttl_seconds must be greater than 0")
    if not hit_rate_buckets:
        raise ValueError("hit_rate_buckets must not be empty")
    if any(bucket < 0 or bucket > 100 for bucket in hit_rate_buckets):
        raise ValueError("hit_rate_buckets must be between 0 and 100")

    return RunConfig(
        scenario=str(scenario),
        iteration_count=iteration_count,
        concurrency=concurrency,
        hit_rate_buckets=hit_rate_buckets,
        ttl_seconds=ttl_seconds,
        include_reference=include_reference,
    )


def _build_baseline_client(settings: ControllerSettings) -> BaselineClient | MongoBaselineClient:
    if settings.baseline_backend == "mongodb":
        return MongoBaselineClient(
            uri=settings.mongodb_uri,
            db_name=settings.mongodb_db_name,
            collection_name=settings.mongodb_collection,
            seed_file=settings.mongodb_seed_file,
            connect_timeout_ms=settings.mongodb_connect_timeout_ms,
        )
    return BaselineClient()

def _collect_benchmark_keys(store: RunStore, iteration_count: int, hit_rate_buckets: list[int]) -> list[str]:
    keys: set[str] = set()
    capped_iteration_count = min(max(iteration_count, 1), 5000)
    buckets = {bucket for bucket in hit_rate_buckets if 0 <= bucket <= 100}
    if not buckets:
        buckets = {0, 50, 100}

    for bucket in buckets:
        for index in range(capped_iteration_count):
            keys.add(f"benchmark:detail:{bucket}-{index}")
    for index in range(capped_iteration_count):
        keys.add(f"benchmark:detail:reference-{index}")

    for run in store.list_runs()[:20]:
        run_id = run.get("run_id")
        if not isinstance(run_id, str):
            continue
        for event in store.read_events(run_id):
            metadata = event.get("metadata", {})
            record_id = metadata.get("record_id")
            if isinstance(record_id, str):
                keys.add(f"benchmark:detail:{record_id}")

    return sorted(keys)


if __name__ == "__main__":
    serve()

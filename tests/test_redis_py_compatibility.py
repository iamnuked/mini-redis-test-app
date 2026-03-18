import socket
import threading
import time

import redis

from internal.config.runtime_config import RuntimeConfig
from internal.server.server import MiniRedisServer
from internal.server.shutdown import ShutdownManager


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


def build_runtime_config(port: int) -> RuntimeConfig:
    return RuntimeConfig.default().with_connection_target(
        host="127.0.0.1",
        port=port,
    )


def run_server_in_thread(config: RuntimeConfig) -> tuple[MiniRedisServer, threading.Thread]:
    shutdown_manager = ShutdownManager()
    server = MiniRedisServer(config=config, shutdown_manager=shutdown_manager)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    wait_for_server(config.host, config.port)
    return server, thread


def test_redis_py_default_connection_supports_ping_and_basic_commands() -> None:
    port = find_free_port()
    config = build_runtime_config(port)
    server, thread = run_server_in_thread(config)

    try:
        client = redis.Redis(host=config.host, port=config.port, decode_responses=True)

        assert client.ping() is True
        assert client.set("compat:key", "value") is True
        assert client.get("compat:key") == "value"
        assert client.hset("compat:user", "name", "mini") == 1
        assert client.hgetall("compat:user") == {"name": "mini"}
        assert client.rpush("compat:list", "a", "b") == 2
        assert client.lrange("compat:list", 0, -1) == ["a", "b"]
    finally:
        client.close()
        server.stop()
        thread.join(timeout=2)


def test_redis_py_resp3_connection_supports_ping_and_hash_commands() -> None:
    port = find_free_port()
    config = build_runtime_config(port)
    server, thread = run_server_in_thread(config)

    try:
        client = redis.Redis(
            host=config.host,
            port=config.port,
            protocol=3,
            decode_responses=True,
        )

        assert client.ping() is True
        assert client.hset("compat:user", "name", "mini") == 1
        assert client.hget("compat:user", "name") == "mini"
        assert client.hgetall("compat:user") == {"name": "mini"}
    finally:
        client.close()
        server.stop()
        thread.join(timeout=2)

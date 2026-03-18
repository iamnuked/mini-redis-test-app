from unittest import mock

from internal.config.runtime_config import RuntimeConfig
from internal.observability.metrics import Metrics
from internal.server.shutdown import ShutdownManager
from internal.server.server import MiniRedisServer


class FakeClientSocket:
    def __init__(self) -> None:
        self.timeout_history: list[float] = []

    def settimeout(self, timeout: float) -> None:
        self.timeout_history.append(timeout)

    def __enter__(self) -> "FakeClientSocket":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        return None


class FakeServerSocket:
    def __init__(self, accept_sequence: list[object]) -> None:
        self.accept_sequence = list(accept_sequence)
        self.timeout_history: list[float] = []
        self.bound_address = None
        self.listening = False
        self.closed = False

    def setsockopt(self, *args) -> None:
        return None

    def bind(self, address) -> None:
        self.bound_address = address

    def listen(self) -> None:
        self.listening = True

    def settimeout(self, timeout: float) -> None:
        self.timeout_history.append(timeout)

    def accept(self):
        next_item = self.accept_sequence.pop(0)
        if isinstance(next_item, BaseException):
            raise next_item
        return next_item

    def close(self) -> None:
        self.closed = True

    def __enter__(self) -> "FakeServerSocket":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        return None


def test_run_starts_and_stops_sweeper_and_applies_idle_timeout() -> None:
    config = RuntimeConfig.default()
    shutdown_manager = ShutdownManager()
    metrics = Metrics()
    client_socket = FakeClientSocket()
    server_socket = FakeServerSocket(
        accept_sequence=[
            (client_socket, ("127.0.0.1", 12345)),
        ]
    )
    sweeper = mock.Mock()
    handler_instance = mock.Mock()

    def handle_side_effect() -> None:
        shutdown_manager.request_shutdown()

    handler_instance.handle.side_effect = handle_side_effect

    with mock.patch("internal.server.server.socket.socket", return_value=server_socket):
        with mock.patch(
            "internal.server.server.ExpirationSweeper",
            return_value=sweeper,
        ):
            with mock.patch(
                "internal.server.server.SessionHandler",
                return_value=handler_instance,
            ) as session_handler_class:
                server = MiniRedisServer(
                    config=config,
                    metrics=metrics,
                    shutdown_manager=shutdown_manager,
                )
                server.run()

    sweeper.start.assert_called_once()
    sweeper.stop.assert_called_once()
    assert server_socket.bound_address == (config.host, config.port)
    assert client_socket.timeout_history == [config.idle_timeout_seconds]
    session_handler_class.assert_called_once()
    assert session_handler_class.call_args.kwargs["read_timeout_seconds"] == (
        config.read_timeout_seconds
    )
    assert session_handler_class.call_args.kwargs["write_timeout_seconds"] == (
        config.write_timeout_seconds
    )


def test_run_rejects_connection_when_limit_is_reached() -> None:
    config = RuntimeConfig.default()
    shutdown_manager = ShutdownManager()
    metrics = Metrics()
    metrics.active_connections = config.max_connections
    client_socket = FakeClientSocket()
    server_socket = FakeServerSocket(
        accept_sequence=[
            (client_socket, ("127.0.0.1", 12345)),
            OSError("shutdown"),
        ]
    )
    sweeper = mock.Mock()

    def error_side_effect(message: str) -> None:
        if message == "connection limit exceeded":
            shutdown_manager.request_shutdown()

    logger = mock.Mock()
    logger.error.side_effect = error_side_effect

    with mock.patch("internal.server.server.socket.socket", return_value=server_socket):
        with mock.patch(
            "internal.server.server.ExpirationSweeper",
            return_value=sweeper,
        ):
            with mock.patch("internal.server.server.SessionHandler") as session_handler_class:
                server = MiniRedisServer(
                    config=config,
                    logger=logger,
                    metrics=metrics,
                    shutdown_manager=shutdown_manager,
                )
                server.run()

    session_handler_class.assert_not_called()
    assert metrics.errors_total == 1
    logger.error.assert_any_call("connection limit exceeded")

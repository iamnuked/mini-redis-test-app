import socket
from unittest import mock

from internal.config.runtime_config import RuntimeConfig
from internal.observability.logger import Logger
from internal.observability.metrics import Metrics
from internal.server.server import MiniRedisServer
from internal.server.shutdown import ShutdownManager


def test_run_starts_and_stops_sweeper_and_applies_idle_timeout() -> None:
    config = RuntimeConfig.default()
    logger = Logger()
    metrics = Metrics()
    shutdown_manager = ShutdownManager()
    accepted_client = mock.Mock(spec=socket.socket)
    accepted_client.__enter__ = mock.Mock(return_value=accepted_client)
    accepted_client.__exit__ = mock.Mock(return_value=None)
    fake_server_socket = mock.Mock(spec=socket.socket)
    fake_server_socket.__enter__ = mock.Mock(return_value=fake_server_socket)
    fake_server_socket.__exit__ = mock.Mock(return_value=None)
    fake_server_socket.accept.side_effect = [
        (accepted_client, ("127.0.0.1", 6379)),
        TimeoutError(),
    ]

    with mock.patch("internal.server.server.socket.socket", return_value=fake_server_socket), \
        mock.patch("internal.server.server.SessionHandler") as session_handler_cls, \
        mock.patch("internal.server.server.ExpirationSweeper") as sweeper_cls:
        session_handler = session_handler_cls.return_value

        def stop_after_handle() -> None:
            shutdown_manager.request_shutdown()

        session_handler.handle.side_effect = stop_after_handle
        sweeper = sweeper_cls.return_value

        server = MiniRedisServer(
            config=config,
            logger=logger,
            metrics=metrics,
            shutdown_manager=shutdown_manager,
        )
        server.run()

    fake_server_socket.bind.assert_called_once_with((config.host, config.port))
    accepted_client.settimeout.assert_called_once_with(config.idle_timeout_seconds)
    sweeper.start.assert_called_once()
    sweeper.stop.assert_called_once()


def test_run_rejects_connection_when_limit_is_reached() -> None:
    config = RuntimeConfig.default()
    logger = Logger()
    metrics = Metrics()
    shutdown_manager = ShutdownManager()
    metrics.increment_active_connections()
    metrics.increment_active_connections()
    accepted_client = mock.Mock(spec=socket.socket)
    accepted_client.__enter__ = mock.Mock(return_value=accepted_client)
    accepted_client.__exit__ = mock.Mock(return_value=None)
    fake_server_socket = mock.Mock(spec=socket.socket)
    fake_server_socket.__enter__ = mock.Mock(return_value=fake_server_socket)
    fake_server_socket.__exit__ = mock.Mock(return_value=None)
    limited_config = RuntimeConfig.default()
    limited_config = limited_config.__class__(
        **{
            **limited_config.__dict__,
            "max_connections": 2,
        }
    )

    with mock.patch("internal.server.server.socket.socket", return_value=fake_server_socket), \
        mock.patch("internal.server.server.SessionHandler") as session_handler_cls, \
        mock.patch("internal.server.server.ExpirationSweeper"):
        accept_calls = iter(
            [
                (accepted_client, ("127.0.0.1", 6379)),
                TimeoutError(),
            ]
        )

        def accept_side_effect():
            result = next(accept_calls)
            if isinstance(result, BaseException):
                shutdown_manager.request_shutdown()
                raise result
            return result

        fake_server_socket.accept.side_effect = accept_side_effect
        server = MiniRedisServer(
            config=limited_config,
            logger=logger,
            metrics=metrics,
            shutdown_manager=shutdown_manager,
        )
        server.run()

    session_handler_cls.assert_not_called()
    assert metrics.errors_total >= 1

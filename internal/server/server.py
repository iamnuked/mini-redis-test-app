import socket
import time

from internal.clock.system_clock import SystemClock
from internal.config.runtime_config import RuntimeConfig
from internal.expiration.expiration_sweeper import ExpirationSweeper
from internal.guard.limits import ResourceLimits
from internal.guard.resource_guard import ResourceGuard
from internal.observability.logger import Logger
from internal.observability.metrics import Metrics
from internal.protocol.resp.protocol_handler import ProtocolHandler
from internal.protocol.resp.response_encoder import RespResponseEncoder
from internal.repository.in_memory_store import InMemoryStoreRepository
from internal.repository.in_memory_ttl import InMemoryTtlRepository
from internal.server.session_handler import SessionHandler
from internal.server.shutdown import ShutdownManager
from internal.service.command_service import CommandService


class MiniRedisServer:
    def __init__(
        self,
        config: RuntimeConfig,
        logger: Logger | None = None,
        metrics: Metrics | None = None,
        shutdown_manager: ShutdownManager | None = None,
    ) -> None:
        self._config = config
        self._logger = logger or Logger()
        self._metrics = metrics or Metrics()
        self._shutdown_manager = shutdown_manager or ShutdownManager()
        self._server_socket: socket.socket | None = None
        self._clock = SystemClock()
        self._store_repository = InMemoryStoreRepository()
        self._ttl_repository = InMemoryTtlRepository()
        self._resource_limits = ResourceLimits(
            max_connections=self._config.max_connections,
            max_request_size_bytes=self._config.max_request_size_bytes,
            max_array_items=self._config.max_array_items,
            max_resp_depth=self._config.max_resp_depth,
            max_blob_size_bytes=self._config.max_blob_size_bytes,
        )
        self._resource_guard = ResourceGuard(self._resource_limits)
        self._command_service = CommandService(
            clock=self._clock,
            store_repository=self._store_repository,
            ttl_repository=self._ttl_repository,
        )
        self._expiration_sweeper = ExpirationSweeper(
            clock=self._clock,
            store_repository=self._store_repository,
            ttl_repository=self._ttl_repository,
            sweep_interval_seconds=self._config.expiration_sweep_interval_seconds,
            sweep_batch_size=self._config.expiration_sweep_batch_size,
        )

    def run(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            self._server_socket = server_socket
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((self._config.host, self._config.port))
            server_socket.listen()
            server_socket.settimeout(self._accept_timeout_seconds())

            self._logger.info(
                f"mini-redis server listening on {self._config.host}:{self._config.port}"
            )
            if self._config.expiration_sweep_enabled:
                self._expiration_sweeper.start()

            try:
                while not self._shutdown_manager.is_shutdown_requested():
                    try:
                        client_socket, client_address = server_socket.accept()
                    except TimeoutError:
                        continue
                    except OSError:
                        if self._shutdown_manager.is_shutdown_requested():
                            break
                        raise

                    with client_socket:
                        client_socket.settimeout(self._config.idle_timeout_seconds)
                        if not self._resource_guard.is_connection_allowed(
                            self._metrics.active_connections
                        ):
                            self._metrics.increment_errors()
                            self._logger.error("connection limit exceeded")
                            continue

                        self._metrics.increment_connections()
                        self._metrics.increment_active_connections()
                        self._logger.info(
                            f"accepted connection from {client_address[0]}:{client_address[1]}"
                        )
                        handler = SessionHandler(
                            client_socket=client_socket,
                            protocol_handler=ProtocolHandler(),
                            command_service=self._command_service,
                            response_encoder=RespResponseEncoder(),
                            resource_guard=self._resource_guard,
                            metrics=self._metrics,
                            logger=self._logger,
                            read_size=self._config.max_request_size_bytes,
                            read_timeout_seconds=self._config.read_timeout_seconds,
                            write_timeout_seconds=self._config.write_timeout_seconds,
                        )
                        try:
                            handler.handle()
                        finally:
                            self._metrics.decrement_active_connections()
            except KeyboardInterrupt:
                self.stop()
            finally:
                self._wait_for_active_connections()
                self._expiration_sweeper.stop()
                self._server_socket = None
                self._logger.info("mini-redis server stopped")

    def stop(self) -> None:
        if self._shutdown_manager.is_shutdown_requested():
            return

        self._logger.info("graceful shutdown requested")
        self._shutdown_manager.request_shutdown()
        if self._server_socket is not None:
            self._server_socket.close()

    def _accept_timeout_seconds(self) -> float:
        return max(1.0, min(float(self._config.idle_timeout_seconds), 1.0))

    def _wait_for_active_connections(self) -> None:
        deadline = time.monotonic() + max(0, self._config.graceful_shutdown_seconds)
        while self._metrics.active_connections > 0 and time.monotonic() < deadline:
            time.sleep(0.05)

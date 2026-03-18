import socket

from internal.command.errors import CommandError
from internal.guard.resource_guard import ResourceGuard
from internal.observability.logger import Logger
from internal.observability.metrics import Metrics
from internal.protocol.resp.protocol_handler import ProtocolHandler
from internal.protocol.resp.response_encoder import RespResponseEncoder
from internal.protocol.resp.types import RespSimpleError
from internal.service.command_service import CommandService


class SessionHandler:
    def __init__(
        self,
        client_socket: socket.socket,
        protocol_handler: ProtocolHandler,
        command_service: CommandService,
        response_encoder: RespResponseEncoder,
        resource_guard: ResourceGuard,
        metrics: Metrics,
        logger: Logger | None = None,
        read_size: int = 4096,
        read_timeout_seconds: int = 5,
        write_timeout_seconds: int = 5,
    ) -> None:
        self._client_socket = client_socket
        self._protocol_handler = protocol_handler
        self._command_service = command_service
        self._response_encoder = response_encoder
        self._resource_guard = resource_guard
        self._metrics = metrics
        self._logger = logger or Logger()
        self._read_size = read_size
        self._read_timeout_seconds = read_timeout_seconds
        self._write_timeout_seconds = write_timeout_seconds

    def handle(self) -> None:
        try:
            request_bytes = self._read_request()
            if not request_bytes:
                return
            if not self._resource_guard.is_request_size_allowed(len(request_bytes)):
                self._metrics.increment_errors()
                self._logger.error("request size limit exceeded")
                return

            self._metrics.increment_requests()
            response = self._process_request(request_bytes)
            self._write_response(response)
        except Exception as error:
            self._metrics.increment_errors()
            self._logger.error(f"session handling failed: {error}")

    def _read_request(self) -> bytes:
        self._client_socket.settimeout(self._read_timeout_seconds)
        return self._client_socket.recv(self._read_size)

    def _process_request(self, request_bytes: bytes) -> bytes:
        protocol_result = self._protocol_handler.handle_with_error_response(request_bytes)
        if protocol_result.has_immediate_response():
            return self._response_encoder.encode(protocol_result.response)

        if protocol_result.command is None:
            raise ValueError("protocol handler returned neither command nor response")

        try:
            service_result = self._command_service.execute(protocol_result.command)
        except CommandError as error:
            service_result = RespSimpleError(message=error.message)
        return self._response_encoder.encode(service_result)

    def _write_response(self, response: bytes) -> None:
        self._client_socket.settimeout(self._write_timeout_seconds)
        self._client_socket.sendall(response)

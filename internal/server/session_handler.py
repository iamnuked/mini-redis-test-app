import socket

from internal.observability.logger import Logger
from internal.protocol.resp.request_decoder import RespRequestDecoder
from internal.protocol.resp.response_encoder import RespResponseEncoder
from internal.service.command_service import CommandService


class SessionHandler:
    def __init__(
        self,
        client_socket: socket.socket,
        request_decoder: RespRequestDecoder,
        command_service: CommandService,
        response_encoder: RespResponseEncoder,
        logger: Logger | None = None,
        read_size: int = 4096,
    ) -> None:
        self._client_socket = client_socket
        self._request_decoder = request_decoder
        self._command_service = command_service
        self._response_encoder = response_encoder
        self._logger = logger or Logger()
        self._read_size = read_size

    def handle(self) -> None:
        try:
            request_bytes = self._read_request()
            if not request_bytes:
                return

            response = self._process_request(request_bytes)
            self._write_response(response)
        except Exception as error:
            self._logger.error(f"session handling failed: {error}")

    def _read_request(self) -> bytes:
        return self._client_socket.recv(self._read_size)

    def _process_request(self, request_bytes: bytes) -> bytes:
        decoded_request = self._request_decoder.decode(request_bytes)
        service_result = self._command_service.execute(decoded_request)  # type: ignore[arg-type]
        return self._response_encoder.encode(service_result)

    def _write_response(self, response: bytes) -> None:
        self._client_socket.sendall(response)

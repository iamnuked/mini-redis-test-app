import socket

from internal.config.runtime_config import RuntimeConfig
from internal.observability.logger import Logger
from internal.protocol.resp.request_decoder import RespRequestDecoder
from internal.protocol.resp.response_encoder import RespResponseEncoder
from internal.server.session_handler import SessionHandler
from internal.service.command_service import CommandService


class MiniRedisServer:
    def __init__(self, config: RuntimeConfig, logger: Logger | None = None) -> None:
        self._config = config
        self._logger = logger or Logger()

    def run(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((self._config.host, self._config.port))
            server_socket.listen()

            self._logger.info(
                f"mini-redis server listening on {self._config.host}:{self._config.port}"
            )

            try:
                while True:
                    client_socket, client_address = server_socket.accept()
                    with client_socket:
                        self._logger.info(
                            f"accepted connection from {client_address[0]}:{client_address[1]}"
                        )
                        handler = SessionHandler(
                            client_socket=client_socket,
                            request_decoder=RespRequestDecoder(),
                            command_service=CommandService(),
                            response_encoder=RespResponseEncoder(),
                            logger=self._logger,
                            read_size=self._config.max_request_size_bytes,
                        )
                        handler.handle()
            except KeyboardInterrupt:
                self._logger.info("mini-redis server stopped")

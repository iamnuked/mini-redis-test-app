from __future__ import annotations

from dataclasses import dataclass

from internal.command.command import Command
from internal.command.errors import CommandError
from internal.command.parser import CommandParser
from internal.command.validator import CommandValidator
from internal.protocol.resp.hello_handler import HelloHandler
from internal.protocol.resp.request_decoder import RespRequestDecoder
from internal.protocol.resp.types import RespSimpleError, RespValue


@dataclass(frozen=True)
class ProtocolHandlerResult:
    command: Command | None = None
    response: RespValue | None = None
    protocol_version: int | None = None

    def has_immediate_response(self) -> bool:
        return self.response is not None


class ProtocolHandler:
    def __init__(
        self,
        decoder: RespRequestDecoder | None = None,
        parser: CommandParser | None = None,
        validator: CommandValidator | None = None,
        hello_handler: HelloHandler | None = None,
    ) -> None:
        self._decoder = decoder or RespRequestDecoder()
        self._parser = parser or CommandParser()
        self._validator = validator or CommandValidator()
        self._hello_handler = hello_handler or HelloHandler()

    def handle(self, data: bytes) -> ProtocolHandlerResult:
        request = self._decoder.decode(data)
        command = self._parser.parse(request)
        self._validator.validate(command)

        if command.name == "HELLO":
            version = int(command.arguments[0])
            return ProtocolHandlerResult(
                response=self._hello_handler.handle(version),
                protocol_version=version,
            )

        return ProtocolHandlerResult(command=command)

    def handle_with_error_response(self, data: bytes) -> ProtocolHandlerResult:
        try:
            return self.handle(data)
        except CommandError as error:
            return ProtocolHandlerResult(response=RespSimpleError(message=error.message))

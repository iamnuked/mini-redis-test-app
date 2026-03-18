from internal.command.command import Command
from internal.command.errors import CommandParseError
from internal.protocol.resp.messages import ERR_EMPTY_COMMAND, ERR_PROTOCOL_ERROR
from internal.protocol.resp.types import RespArray, RespBlobString, RespNumber, RespSimpleString


class CommandParser:
    def parse(self, request: RespArray) -> Command:
        if not request.items:
            raise CommandParseError(ERR_EMPTY_COMMAND)

        parts = tuple(self._coerce_token(item) for item in request.items)
        command_name = parts[0].strip()
        if not command_name:
            raise CommandParseError(ERR_EMPTY_COMMAND)

        return Command(name=command_name.upper(), arguments=parts[1:])

    def _coerce_token(
        self,
        item: RespBlobString | RespSimpleString | RespNumber,
    ) -> str:
        if isinstance(item, (RespBlobString, RespSimpleString)):
            return item.value

        if isinstance(item, RespNumber):
            return str(item.value)

        raise CommandParseError(ERR_PROTOCOL_ERROR)

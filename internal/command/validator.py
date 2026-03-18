from internal.command.command import Command
from internal.command.errors import CommandValidationError
from internal.protocol.resp.messages import (
    ERR_INVALID_INTEGER,
    ERR_INVALID_TTL,
    ERR_UNSUPPORTED_COMMAND,
    ERR_WRONG_NUMBER_OF_ARGUMENTS,
)


class CommandValidator:
    _SUPPORTED_ARITY = {
        "HELLO": 1,
        "SET": 2,
        "GET": 1,
        "DEL": 1,
        "EXPIRE": 2,
        "TTL": 1,
    }

    def validate(self, command: Command) -> None:
        if command.name not in self._SUPPORTED_ARITY:
            raise CommandValidationError(ERR_UNSUPPORTED_COMMAND)
        if len(command.arguments) != self._SUPPORTED_ARITY[command.name]:
            raise CommandValidationError(ERR_WRONG_NUMBER_OF_ARGUMENTS)

        if command.name == "HELLO":
            self._validate_integer_argument(command.arguments[0])

        if command.name == "EXPIRE":
            seconds = self._validate_integer_argument(command.arguments[1])
            if seconds <= 0:
                raise CommandValidationError(ERR_INVALID_TTL)

    def _validate_integer_argument(self, value: str) -> int:
        try:
            return int(value)
        except ValueError as exc:
            raise CommandValidationError(ERR_INVALID_INTEGER) from exc

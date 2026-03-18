from internal.command.command import Command
from internal.command.errors import CommandValidationError


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
            raise CommandValidationError("unsupported command")
        if len(command.arguments) != self._SUPPORTED_ARITY[command.name]:
            raise CommandValidationError("wrong number of arguments")

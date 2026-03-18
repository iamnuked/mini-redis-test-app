from internal.command.command import Command
from internal.command.errors import CommandValidationError
from internal.protocol.resp.messages import (
    ERR_INVALID_DB,
    ERR_INVALID_FLOAT,
    ERR_INVALID_INTEGER,
    ERR_INVALID_TTL,
    ERR_UNSUPPORTED_CLIENT_SUBCOMMAND,
    ERR_UNSUPPORTED_COMMAND,
    ERR_WRONG_NUMBER_OF_ARGUMENTS,
)


class CommandValidator:
    _SUPPORTED_ARITY = {
        "HELLO": 1,
        "AUTH": 1,
        "SELECT": 1,
        "SET": 2,
        "GET": 1,
        "DEL": 1,
        "EXPIRE": 2,
        "TTL": 1,
        "HSET": 3,
        "HGET": 2,
        "HDEL": 2,
        "HGETALL": 1,
        "LPOP": 1,
        "RPOP": 1,
        "LRANGE": 3,
        "SMEMBERS": 1,
        "SISMEMBER": 2,
        "ZRANGE": 3,
        "ZSCORE": 2,
    }
    _MIN_ARITY = {
        "PING": 0,
        "CLIENT": 1,
        "LPUSH": 2,
        "RPUSH": 2,
        "SADD": 2,
        "SREM": 2,
        "ZADD": 3,
        "ZREM": 2,
    }

    def validate(self, command: Command) -> None:
        if command.name not in self._SUPPORTED_ARITY and command.name not in self._MIN_ARITY:
            raise CommandValidationError(ERR_UNSUPPORTED_COMMAND)

        if command.name in self._SUPPORTED_ARITY:
            if len(command.arguments) != self._SUPPORTED_ARITY[command.name]:
                raise CommandValidationError(ERR_WRONG_NUMBER_OF_ARGUMENTS)
        elif len(command.arguments) < self._MIN_ARITY[command.name]:
            raise CommandValidationError(ERR_WRONG_NUMBER_OF_ARGUMENTS)

        if command.name == "HELLO":
            self._validate_integer_argument(command.arguments[0])

        if command.name == "AUTH":
            return

        if command.name == "EXPIRE":
            seconds = self._validate_integer_argument(command.arguments[1])
            if seconds <= 0:
                raise CommandValidationError(ERR_INVALID_TTL)

        if command.name == "SELECT":
            db_index = self._validate_integer_argument(command.arguments[0])
            if db_index < 0:
                raise CommandValidationError(ERR_INVALID_DB)

        if command.name == "LRANGE":
            self._validate_integer_argument(command.arguments[1])
            self._validate_integer_argument(command.arguments[2])

        if command.name == "ZRANGE":
            self._validate_integer_argument(command.arguments[1])
            self._validate_integer_argument(command.arguments[2])

        if command.name == "ZADD":
            if len(command.arguments) % 2 == 0:
                raise CommandValidationError(ERR_WRONG_NUMBER_OF_ARGUMENTS)
            for index in range(1, len(command.arguments), 2):
                self._validate_float_argument(command.arguments[index])

        if command.name == "PING" and len(command.arguments) > 1:
            raise CommandValidationError(ERR_WRONG_NUMBER_OF_ARGUMENTS)

        if command.name == "CLIENT":
            subcommand = command.arguments[0].upper()
            if subcommand == "SETNAME":
                if len(command.arguments) != 2:
                    raise CommandValidationError(ERR_WRONG_NUMBER_OF_ARGUMENTS)
                return
            if subcommand == "SETINFO":
                if len(command.arguments) != 3:
                    raise CommandValidationError(ERR_WRONG_NUMBER_OF_ARGUMENTS)
                return
            if subcommand == "MAINT_NOTIFICATIONS":
                if len(command.arguments) < 2:
                    raise CommandValidationError(ERR_WRONG_NUMBER_OF_ARGUMENTS)
                return
            raise CommandValidationError(ERR_UNSUPPORTED_CLIENT_SUBCOMMAND)

    def _validate_integer_argument(self, value: str) -> int:
        try:
            return int(value)
        except ValueError as exc:
            raise CommandValidationError(ERR_INVALID_INTEGER) from exc

    def _validate_float_argument(self, value: str) -> float:
        try:
            return float(value)
        except ValueError as exc:
            raise CommandValidationError(ERR_INVALID_FLOAT) from exc

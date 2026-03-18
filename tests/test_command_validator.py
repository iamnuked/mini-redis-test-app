import pytest

from internal.command.command import Command
from internal.command.errors import CommandValidationError
from internal.command.validator import CommandValidator
from internal.protocol.resp.messages import (
    ERR_INVALID_INTEGER,
    ERR_INVALID_TTL,
    ERR_UNSUPPORTED_COMMAND,
    ERR_WRONG_NUMBER_OF_ARGUMENTS,
)


def test_validate_accepts_supported_command() -> None:
    validator = CommandValidator()

    validator.validate(Command(name="SET", arguments=("key", "value")))


def test_validate_rejects_unsupported_command() -> None:
    validator = CommandValidator()

    with pytest.raises(CommandValidationError, match=ERR_UNSUPPORTED_COMMAND):
        validator.validate(Command(name="NOPE", arguments=()))


def test_validate_rejects_wrong_arity() -> None:
    validator = CommandValidator()

    with pytest.raises(CommandValidationError, match=ERR_WRONG_NUMBER_OF_ARGUMENTS):
        validator.validate(Command(name="GET", arguments=("key", "extra")))


def test_validate_rejects_non_integer_expire() -> None:
    validator = CommandValidator()

    with pytest.raises(CommandValidationError, match=ERR_INVALID_INTEGER):
        validator.validate(Command(name="EXPIRE", arguments=("key", "abc")))


def test_validate_rejects_non_positive_expire() -> None:
    validator = CommandValidator()

    with pytest.raises(CommandValidationError, match=ERR_INVALID_TTL):
        validator.validate(Command(name="EXPIRE", arguments=("key", "0")))

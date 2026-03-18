import pytest

from internal.clock.fake_clock import FakeClock
from internal.command.command import Command
from internal.command.errors import CommandValidationError
from internal.protocol.resp.messages import (
    ERR_INVALID_INTEGER,
    ERR_INVALID_TTL,
    ERR_UNSUPPORTED_COMMAND,
    RESP_OK,
)
from internal.protocol.resp.types import RespBlobString, RespNull, RespNumber, RespSimpleString
from internal.repository.in_memory_store import InMemoryStoreRepository
from internal.repository.in_memory_ttl import InMemoryTtlRepository
from internal.service.command_service import CommandService


def create_command_service() -> CommandService:
    return CommandService(
        clock=FakeClock(current_time=100.0),
        store_repository=InMemoryStoreRepository(),
        ttl_repository=InMemoryTtlRepository(),
    )


def test_execute_set_returns_simple_string() -> None:
    service = create_command_service()

    response = service.execute(Command(name="SET", arguments=("key", "value")))

    assert response == RespSimpleString(value=RESP_OK)


def test_execute_get_returns_blob_string_for_existing_key() -> None:
    service = create_command_service()
    service.execute(Command(name="SET", arguments=("key", "value")))

    response = service.execute(Command(name="GET", arguments=("key",)))

    assert response == RespBlobString(value="value")


def test_execute_get_returns_null_for_missing_key() -> None:
    service = create_command_service()

    response = service.execute(Command(name="GET", arguments=("missing",)))

    assert response == RespNull()


def test_execute_del_returns_number() -> None:
    service = create_command_service()
    service.execute(Command(name="SET", arguments=("key", "value")))

    response = service.execute(Command(name="DEL", arguments=("key",)))

    assert response == RespNumber(value=1)


def test_execute_expire_returns_number() -> None:
    service = create_command_service()
    service.execute(Command(name="SET", arguments=("key", "value")))

    response = service.execute(Command(name="EXPIRE", arguments=("key", "10")))

    assert response == RespNumber(value=1)


def test_execute_ttl_returns_number() -> None:
    service = create_command_service()
    service.execute(Command(name="SET", arguments=("key", "value")))
    service.execute(Command(name="EXPIRE", arguments=("key", "10")))

    response = service.execute(Command(name="TTL", arguments=("key",)))

    assert response == RespNumber(value=10)


def test_execute_rejects_unsupported_command() -> None:
    service = create_command_service()

    with pytest.raises(CommandValidationError, match=ERR_UNSUPPORTED_COMMAND):
        service.execute(Command(name="NOPE", arguments=()))


def test_execute_rejects_non_integer_expire() -> None:
    service = create_command_service()

    with pytest.raises(CommandValidationError, match=ERR_INVALID_INTEGER):
        service.execute(Command(name="EXPIRE", arguments=("key", "abc")))


def test_execute_rejects_non_positive_expire() -> None:
    service = create_command_service()

    with pytest.raises(CommandValidationError, match=ERR_INVALID_TTL):
        service.execute(Command(name="EXPIRE", arguments=("key", "0")))

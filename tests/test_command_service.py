import pytest

from internal.clock.fake_clock import FakeClock
from internal.command.command import Command
from internal.command.errors import CommandValidationError
from internal.protocol.resp.messages import (
    ERR_UNSUPPORTED_COMMAND,
    ERR_WRONG_TYPE,
    RESP_OK,
)
from internal.protocol.resp.types import (
    RespArray,
    RespBlobString,
    RespMap,
    RespNull,
    RespNumber,
    RespSimpleString,
)
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


def test_execute_hset_and_hget() -> None:
    service = create_command_service()

    set_response = service.execute(Command(name="HSET", arguments=("user", "name", "mini")))
    get_response = service.execute(Command(name="HGET", arguments=("user", "name")))

    assert set_response == RespNumber(value=1)
    assert get_response == RespBlobString(value="mini")


def test_execute_hgetall_returns_map() -> None:
    service = create_command_service()
    service.execute(Command(name="HSET", arguments=("user", "name", "mini")))
    service.execute(Command(name="HSET", arguments=("user", "role", "admin")))

    response = service.execute(Command(name="HGETALL", arguments=("user",)))

    assert response == RespMap(
        entries=(
            (RespBlobString(value="name"), RespBlobString(value="mini")),
            (RespBlobString(value="role"), RespBlobString(value="admin")),
        )
    )


def test_execute_hgetall_returns_fields_in_sorted_order() -> None:
    service = create_command_service()
    service.execute(Command(name="HSET", arguments=("user", "zeta", "last")))
    service.execute(Command(name="HSET", arguments=("user", "alpha", "first")))
    service.execute(Command(name="HSET", arguments=("user", "middle", "mid")))

    response = service.execute(Command(name="HGETALL", arguments=("user",)))

    assert response == RespMap(
        entries=(
            (RespBlobString(value="alpha"), RespBlobString(value="first")),
            (RespBlobString(value="middle"), RespBlobString(value="mid")),
            (RespBlobString(value="zeta"), RespBlobString(value="last")),
        )
    )


def test_execute_lpush_and_lrange() -> None:
    service = create_command_service()
    service.execute(Command(name="LPUSH", arguments=("queue", "a", "b", "c")))

    response = service.execute(Command(name="LRANGE", arguments=("queue", "0", "-1")))

    assert response == RespArray(
        items=(
            RespBlobString(value="c"),
            RespBlobString(value="b"),
            RespBlobString(value="a"),
        )
    )


def test_execute_sadd_and_smembers() -> None:
    service = create_command_service()
    response = service.execute(Command(name="SADD", arguments=("tags", "redis", "redis", "mini")))
    members = service.execute(Command(name="SMEMBERS", arguments=("tags",)))

    assert response == RespNumber(value=2)
    assert members == RespArray(
        items=(
            RespBlobString(value="mini"),
            RespBlobString(value="redis"),
        )
    )


def test_execute_smembers_returns_members_in_sorted_order() -> None:
    service = create_command_service()
    service.execute(Command(name="SADD", arguments=("tags", "zeta", "alpha", "middle")))

    response = service.execute(Command(name="SMEMBERS", arguments=("tags",)))

    assert response == RespArray(
        items=(
            RespBlobString(value="alpha"),
            RespBlobString(value="middle"),
            RespBlobString(value="zeta"),
        )
    )


def test_execute_zadd_and_zrange() -> None:
    service = create_command_service()
    service.execute(Command(name="ZADD", arguments=("rank", "2", "beta", "1", "alpha")))

    response = service.execute(Command(name="ZRANGE", arguments=("rank", "0", "-1")))

    assert response == RespArray(
        items=(
            RespBlobString(value="alpha"),
            RespBlobString(value="beta"),
        )
    )


def test_execute_zrange_breaks_equal_scores_by_member_name() -> None:
    service = create_command_service()
    service.execute(
        Command(
            name="ZADD",
            arguments=("rank", "1", "delta", "1", "alpha", "1", "charlie"),
        )
    )

    response = service.execute(Command(name="ZRANGE", arguments=("rank", "0", "-1")))

    assert response == RespArray(
        items=(
            RespBlobString(value="alpha"),
            RespBlobString(value="charlie"),
            RespBlobString(value="delta"),
        )
    )


def test_execute_zscore_returns_blob_string() -> None:
    service = create_command_service()
    service.execute(Command(name="ZADD", arguments=("rank", "1.5", "alpha")))

    response = service.execute(Command(name="ZSCORE", arguments=("rank", "alpha")))

    assert response == RespBlobString(value="1.5")


def test_execute_returns_wrongtype_for_mismatched_command() -> None:
    service = create_command_service()
    service.execute(Command(name="SET", arguments=("key", "value")))

    with pytest.raises(CommandValidationError, match=ERR_WRONG_TYPE):
        service.execute(Command(name="HGET", arguments=("key", "field")))


def test_execute_hdel_removes_empty_hash_and_ttl() -> None:
    service = create_command_service()
    service.execute(Command(name="HSET", arguments=("user", "name", "mini")))
    service.execute(Command(name="EXPIRE", arguments=("user", "10")))

    delete_response = service.execute(Command(name="HDEL", arguments=("user", "name")))
    ttl_response = service.execute(Command(name="TTL", arguments=("user",)))
    get_all_response = service.execute(Command(name="HGETALL", arguments=("user",)))

    assert delete_response == RespNumber(value=1)
    assert ttl_response == RespNumber(value=-2)
    assert get_all_response == RespMap(entries=())


def test_execute_lpop_removes_empty_list_and_ttl() -> None:
    service = create_command_service()
    service.execute(Command(name="RPUSH", arguments=("queue", "job-1")))
    service.execute(Command(name="EXPIRE", arguments=("queue", "10")))

    pop_response = service.execute(Command(name="LPOP", arguments=("queue",)))
    ttl_response = service.execute(Command(name="TTL", arguments=("queue",)))
    range_response = service.execute(Command(name="LRANGE", arguments=("queue", "0", "-1")))

    assert pop_response == RespBlobString(value="job-1")
    assert ttl_response == RespNumber(value=-2)
    assert range_response == RespArray(items=())


def test_execute_srem_removes_empty_set_and_ttl() -> None:
    service = create_command_service()
    service.execute(Command(name="SADD", arguments=("tags", "redis")))
    service.execute(Command(name="EXPIRE", arguments=("tags", "10")))

    remove_response = service.execute(Command(name="SREM", arguments=("tags", "redis")))
    ttl_response = service.execute(Command(name="TTL", arguments=("tags",)))
    members_response = service.execute(Command(name="SMEMBERS", arguments=("tags",)))

    assert remove_response == RespNumber(value=1)
    assert ttl_response == RespNumber(value=-2)
    assert members_response == RespArray(items=())


def test_execute_zrem_removes_empty_zset_and_ttl() -> None:
    service = create_command_service()
    service.execute(Command(name="ZADD", arguments=("rank", "1", "alpha")))
    service.execute(Command(name="EXPIRE", arguments=("rank", "10")))

    remove_response = service.execute(Command(name="ZREM", arguments=("rank", "alpha")))
    ttl_response = service.execute(Command(name="TTL", arguments=("rank",)))
    range_response = service.execute(Command(name="ZRANGE", arguments=("rank", "0", "-1")))

    assert remove_response == RespNumber(value=1)
    assert ttl_response == RespNumber(value=-2)
    assert range_response == RespArray(items=())


def test_execute_set_overrides_existing_hash_and_clears_ttl() -> None:
    service = create_command_service()
    service.execute(Command(name="HSET", arguments=("key", "field", "value")))
    service.execute(Command(name="EXPIRE", arguments=("key", "10")))

    set_response = service.execute(Command(name="SET", arguments=("key", "string-value")))
    get_response = service.execute(Command(name="GET", arguments=("key",)))
    ttl_response = service.execute(Command(name="TTL", arguments=("key",)))

    assert set_response == RespSimpleString(value=RESP_OK)
    assert get_response == RespBlobString(value="string-value")
    assert ttl_response == RespNumber(value=-1)


def test_execute_expires_hash_key_and_returns_empty_read_result_after_expiration() -> None:
    service = create_command_service()
    service.execute(Command(name="HSET", arguments=("user", "name", "mini")))
    service.execute(Command(name="EXPIRE", arguments=("user", "10")))
    service._expire_service._clock.advance(11.0)

    get_response = service.execute(Command(name="HGET", arguments=("user", "name")))
    ttl_response = service.execute(Command(name="TTL", arguments=("user",)))

    assert get_response == RespNull()
    assert ttl_response == RespNumber(value=-2)


def test_execute_lrange_handles_negative_indexes_and_reversed_range() -> None:
    service = create_command_service()
    service.execute(Command(name="RPUSH", arguments=("queue", "a", "b", "c", "d")))

    tail_response = service.execute(Command(name="LRANGE", arguments=("queue", "-2", "-1")))
    empty_response = service.execute(Command(name="LRANGE", arguments=("queue", "3", "1")))

    assert tail_response == RespArray(
        items=(
            RespBlobString(value="c"),
            RespBlobString(value="d"),
        )
    )
    assert empty_response == RespArray(items=())


def test_execute_zadd_returns_zero_when_updating_existing_member() -> None:
    service = create_command_service()
    service.execute(Command(name="ZADD", arguments=("rank", "1", "alpha")))

    update_response = service.execute(Command(name="ZADD", arguments=("rank", "2", "alpha")))
    score_response = service.execute(Command(name="ZSCORE", arguments=("rank", "alpha")))

    assert update_response == RespNumber(value=0)
    assert score_response == RespBlobString(value="2")


def test_execute_wrongtype_for_other_data_structure_commands() -> None:
    service = create_command_service()
    service.execute(Command(name="SET", arguments=("key", "value")))

    wrongtype_commands = [
        Command(name="LPUSH", arguments=("key", "a")),
        Command(name="SADD", arguments=("key", "member")),
        Command(name="ZADD", arguments=("key", "1", "member")),
    ]

    for command in wrongtype_commands:
        with pytest.raises(CommandValidationError, match=ERR_WRONG_TYPE):
            service.execute(command)

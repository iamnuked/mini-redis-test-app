from internal.clock.clock import Clock
from internal.command.command import Command
from internal.command.errors import CommandValidationError
from internal.expiration.expiration_manager import ExpirationManager
from internal.expiration.ttl_calculator import TtlCalculator
from internal.protocol.resp.messages import (
    ERR_UNSUPPORTED_COMMAND,
    ERR_WRONG_TYPE,
)
from internal.protocol.resp.types import (
    RespBlobString,
    RespArray,
    RespMap,
    RespNull,
    RespNumber,
    RespSimpleString,
    RespValue,
)
from internal.repository.store_repository import StoreRepository
from internal.repository.ttl_repository import TtlRepository
from internal.repository.value_entry import ValueEntry, ValueType
from internal.service.del_service import DelService
from internal.service.expire_service import ExpireService
from internal.service.get_service import GetService
from internal.service.set_service import SetService
from internal.service.ttl_service import TtlService


class CommandService:
    def __init__(
        self,
        clock: Clock,
        store_repository: StoreRepository,
        ttl_repository: TtlRepository,
    ) -> None:
        ttl_calculator = TtlCalculator()
        expiration_manager = ExpirationManager(
            clock=clock,
            ttl_calculator=ttl_calculator,
            store_repository=store_repository,
            ttl_repository=ttl_repository,
        )
        self._store_repository = store_repository
        self._ttl_repository = ttl_repository
        self._expiration_manager = expiration_manager
        self._set_service = SetService(store_repository, ttl_repository)
        self._get_service = GetService(store_repository, expiration_manager)
        self._del_service = DelService(
            store_repository,
            ttl_repository,
            expiration_manager,
        )
        self._expire_service = ExpireService(
            clock,
            ttl_calculator,
            store_repository,
            ttl_repository,
            expiration_manager,
        )
        self._ttl_service = TtlService(
            store_repository,
            ttl_repository,
            expiration_manager,
        )

    def execute(self, command: Command) -> RespValue:
        if command.name == "SET":
            return RespSimpleString(
                value=self._set_service.execute(command.arguments[0], command.arguments[1])
            )
        if command.name == "GET":
            entry = self._get_service.execute(command.arguments[0])
            if entry is None:
                return RespNull()
            return RespBlobString(value=self._require_string(entry))
        if command.name == "DEL":
            return RespNumber(
                value=self._del_service.execute(command.arguments[0]),
            )
        if command.name == "EXPIRE":
            return RespNumber(
                value=self._expire_service.execute(
                    command.arguments[0],
                    int(command.arguments[1]),
                ),
            )
        if command.name == "TTL":
            return RespNumber(
                value=self._ttl_service.execute(command.arguments[0]),
            )
        if command.name == "HSET":
            return RespNumber(
                value=self._execute_hset(
                    command.arguments[0],
                    command.arguments[1],
                    command.arguments[2],
                )
            )
        if command.name == "HGET":
            value = self._execute_hget(command.arguments[0], command.arguments[1])
            if value is None:
                return RespNull()
            return RespBlobString(value=value)
        if command.name == "HDEL":
            return RespNumber(value=self._execute_hdel(command.arguments[0], command.arguments[1]))
        if command.name == "HGETALL":
            return self._execute_hgetall(command.arguments[0])
        if command.name == "LPUSH":
            return RespNumber(value=self._execute_lpush(command.arguments[0], command.arguments[1:]))
        if command.name == "RPUSH":
            return RespNumber(value=self._execute_rpush(command.arguments[0], command.arguments[1:]))
        if command.name == "LPOP":
            value = self._execute_lpop(command.arguments[0])
            if value is None:
                return RespNull()
            return RespBlobString(value=value)
        if command.name == "RPOP":
            value = self._execute_rpop(command.arguments[0])
            if value is None:
                return RespNull()
            return RespBlobString(value=value)
        if command.name == "LRANGE":
            return self._execute_lrange(
                command.arguments[0],
                int(command.arguments[1]),
                int(command.arguments[2]),
            )
        if command.name == "SADD":
            return RespNumber(value=self._execute_sadd(command.arguments[0], command.arguments[1:]))
        if command.name == "SREM":
            return RespNumber(value=self._execute_srem(command.arguments[0], command.arguments[1:]))
        if command.name == "SMEMBERS":
            return self._execute_smembers(command.arguments[0])
        if command.name == "SISMEMBER":
            return RespNumber(value=self._execute_sismember(command.arguments[0], command.arguments[1]))
        if command.name == "ZADD":
            return RespNumber(value=self._execute_zadd(command.arguments[0], command.arguments[1:]))
        if command.name == "ZREM":
            return RespNumber(value=self._execute_zrem(command.arguments[0], command.arguments[1:]))
        if command.name == "ZRANGE":
            return self._execute_zrange(
                command.arguments[0],
                int(command.arguments[1]),
                int(command.arguments[2]),
            )
        if command.name == "ZSCORE":
            value = self._execute_zscore(command.arguments[0], command.arguments[1])
            if value is None:
                return RespNull()
            return RespBlobString(value=value)
        raise CommandValidationError(ERR_UNSUPPORTED_COMMAND)

    def _require_string(self, entry: ValueEntry) -> str:
        if entry.value_type is not ValueType.STRING:
            raise CommandValidationError(ERR_WRONG_TYPE)
        return entry.value

    def _get_live_entry(self, key: str) -> ValueEntry | None:
        self._expiration_manager.purge_if_expired(key)
        return self._store_repository.get(key)

    def _get_typed_entry(self, key: str, value_type: ValueType) -> ValueEntry | None:
        entry = self._get_live_entry(key)
        if entry is None:
            return None
        if entry.value_type is not value_type:
            raise CommandValidationError(ERR_WRONG_TYPE)
        return entry

    def _delete_entry_and_ttl(self, key: str) -> None:
        self._store_repository.delete(key)
        self._ttl_repository.delete_expiration(key)

    def _execute_hset(self, key: str, field: str, value: str) -> int:
        entry = self._get_typed_entry(key, ValueType.HASH)
        if entry is None:
            hash_value: dict[str, str] = {}
            self._store_repository.set(
                key,
                ValueEntry(value_type=ValueType.HASH, value=hash_value),
            )
        else:
            hash_value = entry.value

        created = 1 if field not in hash_value else 0
        hash_value[field] = value
        return created

    def _execute_hget(self, key: str, field: str) -> str | None:
        entry = self._get_typed_entry(key, ValueType.HASH)
        if entry is None:
            return None
        return entry.value.get(field)

    def _execute_hdel(self, key: str, field: str) -> int:
        entry = self._get_typed_entry(key, ValueType.HASH)
        if entry is None:
            return 0
        removed = 1 if field in entry.value else 0
        entry.value.pop(field, None)
        if not entry.value:
            self._delete_entry_and_ttl(key)
        return removed

    def _execute_hgetall(self, key: str) -> RespMap:
        entry = self._get_typed_entry(key, ValueType.HASH)
        if entry is None:
            return RespMap(entries=())

        items = tuple(
            (
                RespBlobString(value=field),
                RespBlobString(value=value),
            )
            for field, value in sorted(entry.value.items())
        )
        return RespMap(entries=items)

    def _get_or_create_list(self, key: str) -> list[str]:
        entry = self._get_typed_entry(key, ValueType.LIST)
        if entry is None:
            list_value: list[str] = []
            self._store_repository.set(
                key,
                ValueEntry(value_type=ValueType.LIST, value=list_value),
            )
            return list_value
        return entry.value

    def _execute_lpush(self, key: str, values: tuple[str, ...]) -> int:
        list_value = self._get_or_create_list(key)
        for value in values:
            list_value.insert(0, value)
        return len(list_value)

    def _execute_rpush(self, key: str, values: tuple[str, ...]) -> int:
        list_value = self._get_or_create_list(key)
        list_value.extend(values)
        return len(list_value)

    def _execute_lpop(self, key: str) -> str | None:
        entry = self._get_typed_entry(key, ValueType.LIST)
        if entry is None or not entry.value:
            return None
        value = entry.value.pop(0)
        if not entry.value:
            self._delete_entry_and_ttl(key)
        return value

    def _execute_rpop(self, key: str) -> str | None:
        entry = self._get_typed_entry(key, ValueType.LIST)
        if entry is None or not entry.value:
            return None
        value = entry.value.pop()
        if not entry.value:
            self._delete_entry_and_ttl(key)
        return value

    def _execute_lrange(self, key: str, start: int, stop: int) -> RespArray:
        entry = self._get_typed_entry(key, ValueType.LIST)
        if entry is None:
            return RespArray(items=())
        values = self._slice_sequence(entry.value, start, stop)
        return RespArray(items=tuple(RespBlobString(value=value) for value in values))

    def _get_or_create_set(self, key: str) -> set[str]:
        entry = self._get_typed_entry(key, ValueType.SET)
        if entry is None:
            set_value: set[str] = set()
            self._store_repository.set(
                key,
                ValueEntry(value_type=ValueType.SET, value=set_value),
            )
            return set_value
        return entry.value

    def _execute_sadd(self, key: str, members: tuple[str, ...]) -> int:
        set_value = self._get_or_create_set(key)
        created = 0
        for member in members:
            if member not in set_value:
                created += 1
            set_value.add(member)
        return created

    def _execute_srem(self, key: str, members: tuple[str, ...]) -> int:
        entry = self._get_typed_entry(key, ValueType.SET)
        if entry is None:
            return 0
        removed = 0
        for member in members:
            if member in entry.value:
                removed += 1
            entry.value.discard(member)
        if not entry.value:
            self._delete_entry_and_ttl(key)
        return removed

    def _execute_smembers(self, key: str) -> RespArray:
        entry = self._get_typed_entry(key, ValueType.SET)
        if entry is None:
            return RespArray(items=())
        return RespArray(
            items=tuple(RespBlobString(value=value) for value in sorted(entry.value))
        )

    def _execute_sismember(self, key: str, member: str) -> int:
        entry = self._get_typed_entry(key, ValueType.SET)
        if entry is None:
            return 0
        return 1 if member in entry.value else 0

    def _get_or_create_zset(self, key: str) -> dict[str, float]:
        entry = self._get_typed_entry(key, ValueType.ZSET)
        if entry is None:
            zset_value: dict[str, float] = {}
            self._store_repository.set(
                key,
                ValueEntry(value_type=ValueType.ZSET, value=zset_value),
            )
            return zset_value
        return entry.value

    def _execute_zadd(self, key: str, arguments: tuple[str, ...]) -> int:
        zset_value = self._get_or_create_zset(key)
        created = 0
        for index in range(0, len(arguments), 2):
            score = float(arguments[index])
            member = arguments[index + 1]
            if member not in zset_value:
                created += 1
            zset_value[member] = score
        return created

    def _execute_zrem(self, key: str, members: tuple[str, ...]) -> int:
        entry = self._get_typed_entry(key, ValueType.ZSET)
        if entry is None:
            return 0
        removed = 0
        for member in members:
            if member in entry.value:
                removed += 1
            entry.value.pop(member, None)
        if not entry.value:
            self._delete_entry_and_ttl(key)
        return removed

    def _execute_zrange(self, key: str, start: int, stop: int) -> RespArray:
        entry = self._get_typed_entry(key, ValueType.ZSET)
        if entry is None:
            return RespArray(items=())
        ordered_members = [
            member
            for member, _score in sorted(entry.value.items(), key=lambda item: (item[1], item[0]))
        ]
        values = self._slice_sequence(ordered_members, start, stop)
        return RespArray(items=tuple(RespBlobString(value=value) for value in values))

    def _execute_zscore(self, key: str, member: str) -> str | None:
        entry = self._get_typed_entry(key, ValueType.ZSET)
        if entry is None:
            return None
        score = entry.value.get(member)
        if score is None:
            return None
        return format(score, "g")

    def _slice_sequence(
        self,
        values: list[str],
        start: int,
        stop: int,
    ) -> list[str]:
        if not values:
            return []

        length = len(values)
        if start < 0:
            start += length
        if stop < 0:
            stop += length

        if start < 0:
            start = 0
        if stop < 0 or start >= length or start > stop:
            return []
        if stop >= length:
            stop = length - 1

        return values[start : stop + 1]

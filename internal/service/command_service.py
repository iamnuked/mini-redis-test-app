from internal.clock.clock import Clock
from internal.command.command import Command
from internal.command.errors import CommandValidationError
from internal.expiration.expiration_manager import ExpirationManager
from internal.expiration.ttl_calculator import TtlCalculator
from internal.protocol.resp.messages import (
    ERR_INVALID_DB,
    ERR_UNSUPPORTED_AUTH,
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
        max_memory_bytes: int | None = None,
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
        self._max_memory_bytes = self._normalize_max_memory_bytes(max_memory_bytes)
        self._access_clock = 0
        self._access_order: dict[str, int] = {}
        self._evicted_keys = 0

    def execute(self, command: Command) -> RespValue:
        if command.name == "AUTH":
            raise CommandValidationError(ERR_UNSUPPORTED_AUTH)
        if command.name == "PING":
            return self._execute_ping(command.arguments)
        if command.name == "SELECT":
            return self._execute_select(command.arguments[0])
        if command.name == "CLIENT":
            return self._execute_client(command.arguments)
        if command.name == "SET":
            key = command.arguments[0]
            response = RespSimpleString(
                value=self._set_service.execute(key, command.arguments[1])
            )
            self._touch_key(key)
            self._ensure_max_memory(protected_keys=(key,))
            return response
        if command.name == "GET":
            key = command.arguments[0]
            entry = self._get_service.execute(key)
            if entry is None:
                self._forget_key(key)
                return RespNull()
            self._touch_key(key)
            return RespBlobString(value=self._require_string(entry))
        if command.name == "DEL":
            key = command.arguments[0]
            deleted = self._del_service.execute(key)
            self._forget_key(key)
            return RespNumber(value=deleted)
        if command.name == "EXPIRE":
            key = command.arguments[0]
            applied = self._expire_service.execute(key, float(command.arguments[1]))
            if applied:
                self._touch_key(key)
            return RespNumber(value=applied)
        if command.name == "TTL":
            return RespNumber(value=self._ttl_service.execute(command.arguments[0]))
        if command.name == "DBSIZE":
            return RespNumber(value=self._execute_dbsize())
        if command.name == "FLUSHDB":
            self._execute_flushdb()
            return RespSimpleString(value=RESP_OK)
        if command.name == "INFO":
            return RespBlobString(value=self._execute_info(command.arguments))
        if command.name == "CONFIG":
            return self._execute_config(command.arguments)
        if command.name == "HSET":
            key = command.arguments[0]
            created = self._execute_hset(key, command.arguments[1], command.arguments[2])
            self._ensure_max_memory(protected_keys=(key,))
            return RespNumber(value=created)
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
            key = command.arguments[0]
            length = self._execute_lpush(key, command.arguments[1:])
            self._ensure_max_memory(protected_keys=(key,))
            return RespNumber(value=length)
        if command.name == "RPUSH":
            key = command.arguments[0]
            length = self._execute_rpush(key, command.arguments[1:])
            self._ensure_max_memory(protected_keys=(key,))
            return RespNumber(value=length)
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
            key = command.arguments[0]
            created = self._execute_sadd(key, command.arguments[1:])
            self._ensure_max_memory(protected_keys=(key,))
            return RespNumber(value=created)
        if command.name == "SREM":
            return RespNumber(value=self._execute_srem(command.arguments[0], command.arguments[1:]))
        if command.name == "SMEMBERS":
            return self._execute_smembers(command.arguments[0])
        if command.name == "SISMEMBER":
            return RespNumber(value=self._execute_sismember(command.arguments[0], command.arguments[1]))
        if command.name == "ZADD":
            key = command.arguments[0]
            created = self._execute_zadd(key, command.arguments[1:])
            self._ensure_max_memory(protected_keys=(key,))
            return RespNumber(value=created)
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

    def _execute_ping(self, arguments: tuple[str, ...]) -> RespValue:
        if not arguments:
            return RespSimpleString(value="PONG")
        return RespBlobString(value=arguments[0])

    def _execute_select(self, db_index: str) -> RespValue:
        if int(db_index) < 0:
            raise CommandValidationError(ERR_INVALID_DB)
        return RespSimpleString(value="OK")

    def _execute_client(self, arguments: tuple[str, ...]) -> RespValue:
        subcommand = arguments[0].upper()
        if subcommand in {"SETNAME", "SETINFO", "MAINT_NOTIFICATIONS"}:
            return RespSimpleString(value="OK")
        raise CommandValidationError(ERR_UNSUPPORTED_COMMAND)

    def _execute_dbsize(self) -> int:
        self._purge_all_expired_keys()
        return len(self._store_repository.list_keys())

    def _execute_flushdb(self) -> None:
        for key in list(self._store_repository.list_keys()):
            self._delete_entry_and_ttl(key)
        self._access_order.clear()
        self._evicted_keys = 0

    def _execute_info(self, arguments: tuple[str, ...]) -> str:
        if arguments and arguments[0].upper() not in {"ALL", "MEMORY"}:
            raise CommandValidationError(ERR_UNSUPPORTED_COMMAND)

        self._purge_all_expired_keys()
        used_memory = self._current_memory_bytes()
        max_memory = self._max_memory_bytes or 0
        key_count = len(self._store_repository.list_keys())

        return "\r\n".join(
            [
                "# Memory",
                f"used_memory:{used_memory}",
                f"maxmemory:{max_memory}",
                f"keys:{key_count}",
                f"evicted_keys:{self._evicted_keys}",
            ]
        )

    def _execute_config(self, arguments: tuple[str, ...]) -> RespValue:
        subcommand = arguments[0].upper()
        parameter = arguments[1].lower()
        if parameter != "maxmemory":
            raise CommandValidationError(ERR_UNSUPPORTED_COMMAND)

        if subcommand == "GET":
            return RespArray(
                items=(
                    RespBlobString(value="maxmemory"),
                    RespBlobString(value=str(self._max_memory_bytes or 0)),
                )
            )

        if subcommand == "SET":
            self._max_memory_bytes = self._normalize_max_memory_bytes(int(arguments[2]))
            self._ensure_max_memory()
            return RespSimpleString(value=RESP_OK)

        raise CommandValidationError(ERR_UNSUPPORTED_COMMAND)

    def _normalize_max_memory_bytes(self, value: int | None) -> int | None:
        if value is None or value <= 0:
            return None
        return value

    def _require_string(self, entry: ValueEntry) -> str:
        if entry.value_type is not ValueType.STRING:
            raise CommandValidationError(ERR_WRONG_TYPE)
        return entry.value

    def _get_live_entry(self, key: str) -> ValueEntry | None:
        self._expiration_manager.purge_if_expired(key)
        entry = self._store_repository.get(key)
        if entry is None:
            self._forget_key(key)
            return None
        self._touch_key(key)
        return entry

    def _get_typed_entry(self, key: str, value_type: ValueType) -> ValueEntry | None:
        entry = self._get_live_entry(key)
        if entry is None:
            return None
        if entry.value_type is not value_type:
            raise CommandValidationError(ERR_WRONG_TYPE)
        return entry

    def _store_entry(self, key: str, entry: ValueEntry) -> None:
        self._store_repository.set(key, entry)
        self._touch_key(key)

    def _delete_entry_and_ttl(self, key: str) -> None:
        self._store_repository.delete(key)
        self._ttl_repository.delete_expiration(key)
        self._forget_key(key)

    def _touch_key(self, key: str) -> None:
        if self._store_repository.get(key) is None:
            self._forget_key(key)
            return
        self._access_clock += 1
        self._access_order[key] = self._access_clock

    def _forget_key(self, key: str) -> None:
        self._access_order.pop(key, None)

    def _purge_all_expired_keys(self) -> None:
        for key in list(self._ttl_repository.list_keys()):
            self._expiration_manager.purge_if_expired(key)
            if self._store_repository.get(key) is None:
                self._forget_key(key)

    def _current_memory_bytes(self) -> int:
        total = 0
        for key in list(self._store_repository.list_keys()):
            entry = self._store_repository.get(key)
            if entry is None:
                self._forget_key(key)
                continue
            total += self._estimate_entry_bytes(key, entry)
        return total

    def _estimate_entry_bytes(self, key: str, entry: ValueEntry) -> int:
        size = len(key.encode("utf-8"))
        if entry.value_type is ValueType.STRING:
            return size + len(entry.value.encode("utf-8"))
        if entry.value_type is ValueType.HASH:
            return size + sum(
                len(field.encode("utf-8")) + len(value.encode("utf-8"))
                for field, value in entry.value.items()
            )
        if entry.value_type is ValueType.LIST:
            return size + sum(len(value.encode("utf-8")) for value in entry.value)
        if entry.value_type is ValueType.SET:
            return size + sum(len(value.encode("utf-8")) for value in entry.value)
        if entry.value_type is ValueType.ZSET:
            return size + sum(
                len(member.encode("utf-8")) + len(format(score, "g").encode("utf-8"))
                for member, score in entry.value.items()
            )
        return size

    def _eviction_candidate(self, protected_keys: tuple[str, ...]) -> str | None:
        protected = set(protected_keys)
        oldest_key: str | None = None
        oldest_access = float("inf")

        for key in self._store_repository.list_keys():
            if key in protected:
                continue
            if self._store_repository.get(key) is None:
                self._forget_key(key)
                continue
            access = self._access_order.get(key, 0)
            if access < oldest_access:
                oldest_access = access
                oldest_key = key

        return oldest_key

    def _ensure_max_memory(self, protected_keys: tuple[str, ...] = ()) -> None:
        if self._max_memory_bytes is None:
            return

        self._purge_all_expired_keys()
        while self._current_memory_bytes() > self._max_memory_bytes:
            key = self._eviction_candidate(protected_keys)
            if key is None:
                break
            self._delete_entry_and_ttl(key)
            self._evicted_keys += 1
        if self._current_memory_bytes() <= self._max_memory_bytes:
            return
        for key in protected_keys:
            if self._current_memory_bytes() <= self._max_memory_bytes:
                break
            if self._store_repository.get(key) is None:
                self._forget_key(key)
                continue
            self._delete_entry_and_ttl(key)
            self._evicted_keys += 1

    def _execute_hset(self, key: str, field: str, value: str) -> int:
        entry = self._get_typed_entry(key, ValueType.HASH)
        if entry is None:
            hash_value: dict[str, str] = {}
            self._store_entry(
                key,
                ValueEntry(value_type=ValueType.HASH, value=hash_value),
            )
        else:
            hash_value = entry.value

        created = 1 if field not in hash_value else 0
        hash_value[field] = value
        self._touch_key(key)
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
            self._store_entry(
                key,
                ValueEntry(value_type=ValueType.LIST, value=list_value),
            )
            return list_value
        return entry.value

    def _execute_lpush(self, key: str, values: tuple[str, ...]) -> int:
        list_value = self._get_or_create_list(key)
        for value in values:
            list_value.insert(0, value)
        self._touch_key(key)
        return len(list_value)

    def _execute_rpush(self, key: str, values: tuple[str, ...]) -> int:
        list_value = self._get_or_create_list(key)
        list_value.extend(values)
        self._touch_key(key)
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
            self._store_entry(
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
        self._touch_key(key)
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
            self._store_entry(
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
        self._touch_key(key)
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

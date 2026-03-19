from __future__ import annotations

import os
from dataclasses import dataclass, field
from math import ceil
from time import monotonic
from typing import Protocol

from internal.arena.common.models import WRONG_TYPE_MESSAGE


@dataclass
class MiniRedisConnectionSettings:
    backend: str = "inmemory"
    host: str = "127.0.0.1"
    port: int = 6379
    db: int = 0
    socket_timeout_seconds: float = 1.0
    decode_responses: bool = True

    @classmethod
    def from_env(cls) -> "MiniRedisConnectionSettings":
        return cls(
            backend=os.getenv("ARENA_REDIS_BACKEND", "inmemory"),
            host=os.getenv("MINI_REDIS_HOST", "127.0.0.1"),
            port=int(os.getenv("MINI_REDIS_PORT", "6379")),
            db=int(os.getenv("MINI_REDIS_DB", "0")),
            socket_timeout_seconds=float(
                os.getenv("MINI_REDIS_SOCKET_TIMEOUT_SECONDS", "1.0")
            ),
        )


class MiniRedisClient(Protocol):
    def set(self, key: str, value: str) -> None:
        ...

    def get(self, key: str) -> str | None:
        ...

    def hset(self, key: str, field_name: str, value: str) -> None:
        ...

    def hget(self, key: str, field_name: str) -> str | None:
        ...

    def hgetall(self, key: str) -> dict[str, str] | None:
        ...

    def delete(self, key: str) -> bool:
        ...

    def expire(self, key: str, ttl_seconds: float) -> bool:
        ...

    def ttl(self, key: str) -> int | None:
        ...

    def ping(self) -> bool:
        ...

    def flushdb(self) -> None:
        ...

    def dbsize(self) -> int:
        ...

    def info_memory(self) -> dict[str, int]:
        ...

    def config_set_maxmemory(self, max_memory_bytes: int) -> None:
        ...

    def config_get_maxmemory(self) -> int:
        ...

    def close(self) -> None:
        ...


@dataclass
class RedisEntry:
    kind: str = "string"
    value: str | None = None
    fields: dict[str, str] = field(default_factory=dict)
    expires_at: float | None = None


@dataclass
class InMemoryMiniRedisClient:
    _entries: dict[str, RedisEntry] = field(default_factory=dict)
    _max_memory_bytes: int | None = None
    _evicted_keys: int = 0
    _access_clock: int = 0
    _access_order: dict[str, int] = field(default_factory=dict)

    def set(self, key: str, value: str) -> None:
        self._purge_expired()
        self._entries[key] = RedisEntry(kind="string", value=value)
        self._touch(key)
        self._enforce_max_memory(protected_keys=(key,))

    def get(self, key: str) -> str | None:
        entry = self._entries.get(key)
        if entry is None:
            return None

        if entry.expires_at is not None and monotonic() >= entry.expires_at:
            self.delete(key)
            return None
        if entry.kind != "string":
            raise TypeError(WRONG_TYPE_MESSAGE)

        self._touch(key)
        return entry.value

    def hset(self, key: str, field_name: str, value: str) -> None:
        self._purge_expired()
        entry = self._entries.get(key)
        if entry is None:
            self._entries[key] = RedisEntry(
                kind="hash",
                fields={field_name: value},
            )
            self._touch(key)
            self._enforce_max_memory(protected_keys=(key,))
            return
        if entry.kind != "hash":
            raise TypeError(WRONG_TYPE_MESSAGE)
        entry.fields[field_name] = value
        self._touch(key)
        self._enforce_max_memory(protected_keys=(key,))

    def hget(self, key: str, field_name: str) -> str | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        if entry.expires_at is not None and monotonic() >= entry.expires_at:
            self.delete(key)
            return None
        if entry.kind != "hash":
            raise TypeError(WRONG_TYPE_MESSAGE)
        self._touch(key)
        return entry.fields.get(field_name)

    def hgetall(self, key: str) -> dict[str, str] | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        if entry.expires_at is not None and monotonic() >= entry.expires_at:
            self.delete(key)
            return None
        if entry.kind != "hash":
            raise TypeError(WRONG_TYPE_MESSAGE)
        self._touch(key)
        return dict(entry.fields)

    def delete(self, key: str) -> bool:
        if key not in self._entries:
            return False
        del self._entries[key]
        self._access_order.pop(key, None)
        return True

    def expire(self, key: str, ttl_seconds: float) -> bool:
        entry = self._entries.get(key)
        if entry is None:
            return False
        entry.expires_at = monotonic() + ttl_seconds
        self._touch(key)
        return True

    def ttl(self, key: str) -> int | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        if entry.expires_at is None:
            return None
        remaining_seconds = ceil(entry.expires_at - monotonic())
        if remaining_seconds <= 0:
            self.delete(key)
            return None
        return remaining_seconds

    def ping(self) -> bool:
        return True

    def flushdb(self) -> None:
        self._entries.clear()
        self._access_order.clear()
        self._evicted_keys = 0

    def dbsize(self) -> int:
        self._purge_expired()
        return len(self._entries)

    def info_memory(self) -> dict[str, int]:
        self._purge_expired()
        return {
            "used_memory": self._used_memory_bytes(),
            "maxmemory": self._max_memory_bytes or 0,
            "keys": len(self._entries),
            "evicted_keys": self._evicted_keys,
        }

    def config_set_maxmemory(self, max_memory_bytes: int) -> None:
        self._max_memory_bytes = max_memory_bytes if max_memory_bytes > 0 else None
        self._enforce_max_memory()

    def config_get_maxmemory(self) -> int:
        return self._max_memory_bytes or 0

    def close(self) -> None:
        return None

    def _purge_expired(self) -> None:
        now = monotonic()
        for key, entry in list(self._entries.items()):
            if entry.expires_at is not None and now >= entry.expires_at:
                self.delete(key)

    def _touch(self, key: str) -> None:
        if key not in self._entries:
            self._access_order.pop(key, None)
            return
        self._access_clock += 1
        self._access_order[key] = self._access_clock

    def _entry_size_bytes(self, key: str, entry: RedisEntry) -> int:
        size = len(key.encode("utf-8"))
        if entry.kind == "string":
            return size + len((entry.value or "").encode("utf-8"))
        return size + sum(
            len(field_name.encode("utf-8")) + len(field_value.encode("utf-8"))
            for field_name, field_value in entry.fields.items()
        )

    def _used_memory_bytes(self) -> int:
        return sum(self._entry_size_bytes(key, entry) for key, entry in self._entries.items())

    def _eviction_candidate(self, protected_keys: tuple[str, ...]) -> str | None:
        protected = set(protected_keys)
        oldest_key: str | None = None
        oldest_access = float("inf")
        for key in self._entries:
            if key in protected:
                continue
            access = self._access_order.get(key, 0)
            if access < oldest_access:
                oldest_access = access
                oldest_key = key
        return oldest_key

    def _enforce_max_memory(self, protected_keys: tuple[str, ...] = ()) -> None:
        if self._max_memory_bytes is None:
            return
        self._purge_expired()
        while self._used_memory_bytes() > self._max_memory_bytes:
            key = self._eviction_candidate(protected_keys)
            if key is None:
                break
            self.delete(key)
            self._evicted_keys += 1


@dataclass
class RedisPyMiniRedisClient:
    settings: MiniRedisConnectionSettings
    _client: object | None = field(init=False, default=None, repr=False)

    def __post_init__(self) -> None:
        self._redis_module = self._load_redis_module()
        self._client = self._build_client()

    def _load_redis_module(self):
        try:
            import redis
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "redis package is required for ARENA_REDIS_BACKEND=redis_py"
            ) from exc
        return redis

    def _build_client(self):
        return self._redis_module.Redis(
            host=self.settings.host,
            port=self.settings.port,
            db=self.settings.db,
            decode_responses=self.settings.decode_responses,
            socket_timeout=self.settings.socket_timeout_seconds,
            socket_connect_timeout=self.settings.socket_timeout_seconds,
        )

    def _get_client(self):
        if self._client is None:
            self._client = self._build_client()
        return self._client

    def set(self, key: str, value: str) -> None:
        self._get_client().set(name=key, value=value)

    def get(self, key: str) -> str | None:
        return self._get_client().get(name=key)

    def hset(self, key: str, field_name: str, value: str) -> None:
        self._get_client().hset(name=key, key=field_name, value=value)

    def hget(self, key: str, field_name: str) -> str | None:
        return self._get_client().hget(name=key, key=field_name)

    def hgetall(self, key: str) -> dict[str, str] | None:
        result = self._get_client().hgetall(name=key)
        return result or None

    def delete(self, key: str) -> bool:
        return bool(self._get_client().delete(key))

    def expire(self, key: str, ttl_seconds: float) -> bool:
        return bool(self._get_client().execute_command("EXPIRE", key, str(ttl_seconds)))

    def ttl(self, key: str) -> int | None:
        result = self._get_client().ttl(key)
        if result is None or result < 0:
            return None
        return int(result)

    def ping(self) -> bool:
        return bool(self._get_client().ping())

    def flushdb(self) -> None:
        self._get_client().execute_command("FLUSHDB")

    def dbsize(self) -> int:
        return int(self._get_client().execute_command("DBSIZE"))

    def info_memory(self) -> dict[str, int]:
        raw = self._get_client().execute_command("INFO", "MEMORY")
        return self._parse_info(raw)

    def config_set_maxmemory(self, max_memory_bytes: int) -> None:
        self._get_client().execute_command(
            "CONFIG",
            "SET",
            "maxmemory",
            str(max(0, max_memory_bytes)),
        )

    def config_get_maxmemory(self) -> int:
        raw = self._get_client().execute_command("CONFIG", "GET", "maxmemory")

        if isinstance(raw, dict):
            return int(raw.get("maxmemory", 0))
        if isinstance(raw, (list, tuple)) and len(raw) >= 2:
            return int(raw[1])
        raise RuntimeError(f"Unexpected CONFIG GET response: {raw!r}")

    def close(self) -> None:
        client = self._client
        if client is None:
            return
        try:
            close = getattr(client, "close", None)
            if callable(close):
                close()
        finally:
            pool = getattr(client, "connection_pool", None)
            disconnect = getattr(pool, "disconnect", None)
            if callable(disconnect):
                disconnect()
            self._client = None

    def _parse_info(self, raw: str | bytes | dict) -> dict[str, int]:
        if isinstance(raw, dict):
            info: dict[str, int] = {}
            for key, value in raw.items():
                try:
                    info[key] = int(value)
                except (TypeError, ValueError):
                    continue
            return info
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")

        info: dict[str, int] = {}
        for line in raw.splitlines():
            if not line or line.startswith("#") or ":" not in line:
                continue
            key, value = line.split(":", 1)
            try:
                info[key] = int(value)
            except ValueError:
                continue
        return info


def build_mini_redis_client(
    settings: MiniRedisConnectionSettings,
) -> MiniRedisClient:
    if settings.backend == "redis_py":
        return RedisPyMiniRedisClient(settings=settings)
    if settings.backend == "inmemory":
        return InMemoryMiniRedisClient()
    raise ValueError(f"Unsupported ARENA_REDIS_BACKEND: {settings.backend}")

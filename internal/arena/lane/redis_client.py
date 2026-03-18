from __future__ import annotations

import os
from dataclasses import dataclass, field
from math import ceil
from time import monotonic
from typing import Protocol


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

    def delete(self, key: str) -> bool:
        ...

    def expire(self, key: str, ttl_seconds: int) -> bool:
        ...

    def ttl(self, key: str) -> int | None:
        ...


@dataclass
class RedisEntry:
    value: str
    expires_at: float | None = None


@dataclass
class InMemoryMiniRedisClient:
    _entries: dict[str, RedisEntry] = field(default_factory=dict)

    def set(self, key: str, value: str) -> None:
        self._entries[key] = RedisEntry(value=value)

    def get(self, key: str) -> str | None:
        entry = self._entries.get(key)
        if entry is None:
            return None

        if entry.expires_at is not None and monotonic() >= entry.expires_at:
            del self._entries[key]
            return None

        return entry.value

    def delete(self, key: str) -> bool:
        if key not in self._entries:
            return False
        del self._entries[key]
        return True

    def expire(self, key: str, ttl_seconds: int) -> bool:
        entry = self._entries.get(key)
        if entry is None:
            return False
        entry.expires_at = monotonic() + ttl_seconds
        return True

    def ttl(self, key: str) -> int | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        if entry.expires_at is None:
            return None
        remaining_seconds = ceil(entry.expires_at - monotonic())
        if remaining_seconds <= 0:
            del self._entries[key]
            return None
        return remaining_seconds


@dataclass
class RedisPyMiniRedisClient:
    settings: MiniRedisConnectionSettings

    def __post_init__(self) -> None:
        self._redis_module = self._load_redis_module()

    def _load_redis_module(self):
        try:
            import redis
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "redis package is required for ARENA_REDIS_BACKEND=redis_py"
            ) from exc
        return redis

    def _create_client(self):
        return self._redis_module.Redis(
            host=self.settings.host,
            port=self.settings.port,
            db=self.settings.db,
            decode_responses=self.settings.decode_responses,
            socket_timeout=self.settings.socket_timeout_seconds,
            socket_connect_timeout=self.settings.socket_timeout_seconds,
        )

    def set(self, key: str, value: str) -> None:
        client = self._create_client()
        try:
            client.set(name=key, value=value)
        finally:
            client.close()

    def get(self, key: str) -> str | None:
        client = self._create_client()
        try:
            return client.get(name=key)
        finally:
            client.close()

    def delete(self, key: str) -> bool:
        client = self._create_client()
        try:
            return bool(client.delete(key))
        finally:
            client.close()

    def expire(self, key: str, ttl_seconds: int) -> bool:
        client = self._create_client()
        try:
            return bool(client.expire(key, ttl_seconds))
        finally:
            client.close()

    def ttl(self, key: str) -> int | None:
        client = self._create_client()
        try:
            result = client.ttl(key)
            if result is None or result < 0:
                return None
            return int(result)
        finally:
            client.close()


def build_mini_redis_client(
    settings: MiniRedisConnectionSettings,
) -> MiniRedisClient:
    if settings.backend == "redis_py":
        return RedisPyMiniRedisClient(settings=settings)
    if settings.backend == "inmemory":
        return InMemoryMiniRedisClient()
    raise ValueError(f"Unsupported ARENA_REDIS_BACKEND: {settings.backend}")

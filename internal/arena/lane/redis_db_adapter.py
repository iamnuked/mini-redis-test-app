from __future__ import annotations

import json
import time
from typing import Iterable

from internal.arena.gateway.models import ArenaRequest, CacheResult, LaneResult
from internal.arena.gateway.models import LaneMetrics
from internal.arena.gateway.models import SeedStateInput
from internal.arena.lane.cache_policy import redis_ttl_for_request
from internal.arena.lane.redis_client import MiniRedisClient
from internal.arena.mongo.repository import ArenaRepository


class RedisDBLaneAdapter:
    lane_name = "redis_db"

    def __init__(
        self,
        redis_client: MiniRedisClient,
        repository: ArenaRepository,
    ) -> None:
        self._redis_client = redis_client
        self._repository = repository

    def _set_answer(self) -> tuple[str, str]:
        return ("OK", "ok")

    def _get_answer(self, value: str | None) -> tuple[str, str]:
        if value is None:
            return ("(nil)", "nil")
        return (value, "value")

    def _delete_answer(self, deleted: bool) -> tuple[str, str]:
        if deleted:
            return ("deleted", "deleted")
        return ("not found", "not_found")

    def _serialize_hash(self, fields: dict[str, str] | None) -> str | None:
        if fields is None:
            return None
        return json.dumps(fields, separators=(",", ":"), sort_keys=True)

    def _ttl_label(self, ttl_seconds: float) -> str:
        return f"{ttl_seconds:g}s"

    def _fill_hash(
        self,
        key: str,
        fields: dict[str, str],
        *,
        ttl_seconds: float | None,
    ) -> float:
        redis_time_ms = 0.0
        for field_name, field_value in fields.items():
            redis_started_at = time.perf_counter()
            self._redis_client.hset(key, field_name, field_value)
            redis_time_ms += (time.perf_counter() - redis_started_at) * 1000
        if ttl_seconds is not None:
            redis_started_at = time.perf_counter()
            self._redis_client.expire(key, ttl_seconds)
            redis_time_ms += (time.perf_counter() - redis_started_at) * 1000
        return redis_time_ms

    async def execute(self, request: ArenaRequest) -> LaneResult:
        started_at = time.perf_counter()
        started_at_ns = time.perf_counter_ns()
        path: list[str] = []
        storage_changes: list[str] = []
        cache = CacheResult()
        mongo_reads = 0
        value_preview: str | None = None
        answer_text: str | None = None
        answer_kind: str | None = None
        db_time_ms = 0.0
        redis_time_ms = 0.0

        try:
            if request.command == "SET":
                db_started_at = time.perf_counter()
                write_state = self._repository.write(request.key, request.value or "")
                db_time_ms += (time.perf_counter() - db_started_at) * 1000
                ttl_seconds = redis_ttl_for_request(request.ttl_enabled, request.ttl_seconds)
                redis_started_at = time.perf_counter()
                self._redis_client.set(request.key, request.value or "")
                redis_time_ms += (time.perf_counter() - redis_started_at) * 1000
                path.extend(["mongo_write", "redis_set"])
                storage_changes.append(f"Mongo document {write_state}")
                storage_changes.append("Redis key upserted")
                if ttl_seconds is not None:
                    redis_started_at = time.perf_counter()
                    ttl_applied = self._redis_client.expire(request.key, ttl_seconds)
                    redis_time_ms += (time.perf_counter() - redis_started_at) * 1000
                    path.append("redis_expire")
                    if ttl_applied:
                        storage_changes.append(
                            f"Redis TTL applied (ttl={self._ttl_label(ttl_seconds)})"
                        )
                    else:
                        storage_changes.append("Redis TTL apply failed")
                value_preview = request.value
                answer_text, answer_kind = self._set_answer()

            elif request.command == "GET":
                path.append("redis_read")
                redis_started_at = time.perf_counter()
                cached_value = self._redis_client.get(request.key)
                redis_time_ms += (time.perf_counter() - redis_started_at) * 1000
                if cached_value is not None:
                    cache.hit = True
                    value_preview = cached_value
                    path.append("redis_hit")
                    storage_changes.extend(["Redis value returned", "Mongo unchanged"])
                    answer_text, answer_kind = self._get_answer(cached_value)
                else:
                    cache.miss = True
                    path.append("mongo_read")
                    mongo_reads = 1
                    db_started_at = time.perf_counter()
                    mongo_value = self._repository.read(request.key)
                    db_time_ms += (time.perf_counter() - db_started_at) * 1000
                    if mongo_value is None:
                        storage_changes.extend(["Redis miss", "Mongo document missing"])
                        answer_text, answer_kind = self._get_answer(None)
                    else:
                        value_preview = mongo_value
                        ttl_seconds = redis_ttl_for_request(
                            request.ttl_enabled,
                            request.ttl_seconds,
                        )
                        redis_started_at = time.perf_counter()
                        self._redis_client.set(request.key, mongo_value)
                        redis_time_ms += (time.perf_counter() - redis_started_at) * 1000
                        path.append("redis_fill")
                        storage_changes.append("Mongo document read")
                        storage_changes.append("Redis key filled")
                        if ttl_seconds is not None:
                            redis_started_at = time.perf_counter()
                            ttl_applied = self._redis_client.expire(request.key, ttl_seconds)
                            redis_time_ms += (time.perf_counter() - redis_started_at) * 1000
                            path.append("redis_expire")
                            if ttl_applied:
                                storage_changes.append(
                                    f"Redis TTL applied (ttl={self._ttl_label(ttl_seconds)})"
                                )
                            else:
                                storage_changes.append("Redis TTL apply failed")
                        answer_text, answer_kind = self._get_answer(mongo_value)

            elif request.command == "HSET":
                field_name = request.field or ""
                db_started_at = time.perf_counter()
                write_state = self._repository.hset(request.key, field_name, request.value or "")
                db_time_ms += (time.perf_counter() - db_started_at) * 1000
                ttl_seconds = redis_ttl_for_request(request.ttl_enabled, request.ttl_seconds)
                redis_started_at = time.perf_counter()
                self._redis_client.hset(request.key, field_name, request.value or "")
                redis_time_ms += (time.perf_counter() - redis_started_at) * 1000
                path.extend(["mongo_write", "redis_set"])
                storage_changes.append(f"Mongo hash field {write_state}")
                storage_changes.append("Redis hash field upserted")
                if ttl_seconds is not None:
                    redis_started_at = time.perf_counter()
                    ttl_applied = self._redis_client.expire(request.key, ttl_seconds)
                    redis_time_ms += (time.perf_counter() - redis_started_at) * 1000
                    path.append("redis_expire")
                    if ttl_applied:
                        storage_changes.append(
                            f"Redis TTL applied (ttl={self._ttl_label(ttl_seconds)})"
                        )
                    else:
                        storage_changes.append("Redis TTL apply failed")
                value_preview = request.value
                answer_text, answer_kind = self._set_answer()

            elif request.command == "HGET":
                field_name = request.field or ""
                path.append("redis_read")
                redis_started_at = time.perf_counter()
                cached_value = self._redis_client.hget(request.key, field_name)
                redis_time_ms += (time.perf_counter() - redis_started_at) * 1000
                if cached_value is not None:
                    cache.hit = True
                    value_preview = cached_value
                    path.append("redis_hit")
                    storage_changes.extend(["Redis hash field returned", "Mongo unchanged"])
                    answer_text, answer_kind = self._get_answer(value_preview)
                else:
                    redis_started_at = time.perf_counter()
                    cached_fields = self._redis_client.hgetall(request.key)
                    redis_time_ms += (time.perf_counter() - redis_started_at) * 1000
                    if cached_fields is not None:
                        cache.hit = True
                        value_preview = None
                        path.append("redis_hit")
                        storage_changes.extend(
                            ["Redis hash field missing", "Mongo unchanged"]
                        )
                        answer_text, answer_kind = self._get_answer(None)
                    else:
                        cache.miss = True
                        path.append("mongo_read")
                        mongo_reads = 1
                        db_started_at = time.perf_counter()
                        mongo_fields = self._repository.hgetall(request.key)
                        db_time_ms += (time.perf_counter() - db_started_at) * 1000
                        if mongo_fields is None:
                            storage_changes.extend(["Redis miss", "Mongo hash missing"])
                            answer_text, answer_kind = self._get_answer(None)
                        else:
                            value_preview = mongo_fields.get(field_name)
                            ttl_seconds = redis_ttl_for_request(
                                request.ttl_enabled,
                                request.ttl_seconds,
                            )
                            redis_time_ms += self._fill_hash(
                                request.key,
                                mongo_fields,
                                ttl_seconds=ttl_seconds,
                            )
                            path.append("redis_fill")
                            if ttl_seconds is not None:
                                path.append("redis_expire")
                                storage_changes.append(
                                    f"Redis TTL applied (ttl={self._ttl_label(ttl_seconds)})"
                                )
                            storage_changes.append("Mongo hash read")
                            storage_changes.append("Redis hash filled")
                            answer_text, answer_kind = self._get_answer(value_preview)

            elif request.command == "HGETALL":
                path.append("redis_read")
                redis_started_at = time.perf_counter()
                cached_fields = self._redis_client.hgetall(request.key)
                redis_time_ms += (time.perf_counter() - redis_started_at) * 1000
                if cached_fields is not None:
                    cache.hit = True
                    value_preview = self._serialize_hash(cached_fields)
                    path.append("redis_hit")
                    storage_changes.extend(["Redis hash returned", "Mongo unchanged"])
                    answer_text, answer_kind = self._get_answer(value_preview)
                else:
                    cache.miss = True
                    path.append("mongo_read")
                    mongo_reads = 1
                    db_started_at = time.perf_counter()
                    mongo_fields = self._repository.hgetall(request.key)
                    db_time_ms += (time.perf_counter() - db_started_at) * 1000
                    if mongo_fields is None:
                        storage_changes.extend(["Redis miss", "Mongo hash missing"])
                        answer_text, answer_kind = self._get_answer(None)
                    else:
                        ttl_seconds = redis_ttl_for_request(
                            request.ttl_enabled,
                            request.ttl_seconds,
                        )
                        redis_time_ms += self._fill_hash(
                            request.key,
                            mongo_fields,
                            ttl_seconds=ttl_seconds,
                        )
                        path.append("redis_fill")
                        if ttl_seconds is not None:
                            path.append("redis_expire")
                            storage_changes.append(
                                f"Redis TTL applied (ttl={self._ttl_label(ttl_seconds)})"
                            )
                        value_preview = self._serialize_hash(mongo_fields)
                        storage_changes.append("Mongo hash read")
                        storage_changes.append("Redis hash filled")
                        answer_text, answer_kind = self._get_answer(value_preview)

            elif request.command == "DEL":
                path.extend(["redis_delete", "mongo_delete"])
                redis_started_at = time.perf_counter()
                redis_deleted = self._redis_client.delete(request.key)
                redis_time_ms += (time.perf_counter() - redis_started_at) * 1000
                db_started_at = time.perf_counter()
                mongo_deleted = self._repository.delete(request.key)
                db_time_ms += (time.perf_counter() - db_started_at) * 1000
                storage_changes.append("Redis key deleted" if redis_deleted else "Redis unchanged")
                storage_changes.append(
                    "Mongo document deleted" if mongo_deleted else "Mongo unchanged"
                )
                answer_text, answer_kind = self._delete_answer(redis_deleted or mongo_deleted)

            service_time_ms = round((time.perf_counter() - started_at) * 1000, 3)
            return LaneResult(
                request_id=request.request_id,
                lane=self.lane_name,
                status="ok",
                latency_ms=service_time_ms,
                answer_text=answer_text,
                answer_kind=answer_kind,
                value_preview=value_preview,
                path=path,
                storage_changes=storage_changes,
                cache=cache,
                mongo_reads=mongo_reads,
                metrics=LaneMetrics(
                    service_time_ms=service_time_ms,
                    db_time_ms=round(db_time_ms, 3),
                    redis_time_ms=round(redis_time_ms, 3),
                    started_at_ns=started_at_ns,
                    finished_at_ns=time.perf_counter_ns(),
                ),
            )
        except Exception as exc:
            service_time_ms = round((time.perf_counter() - started_at) * 1000, 3)
            return LaneResult(
                request_id=request.request_id,
                lane=self.lane_name,
                status="error",
                latency_ms=service_time_ms,
                answer_text=f"error: {exc}",
                answer_kind="error",
                value_preview=str(exc),
                path=path,
                storage_changes=storage_changes or ["Redis + DB lane execution failed"],
                cache=cache,
                mongo_reads=mongo_reads,
                metrics=LaneMetrics(
                    service_time_ms=service_time_ms,
                    db_time_ms=round(db_time_ms, 3),
                    redis_time_ms=round(redis_time_ms, 3),
                    started_at_ns=started_at_ns,
                    finished_at_ns=time.perf_counter_ns(),
                ),
            )

    def clear(self, keys: Iterable[str], *, full_reset: bool = False) -> None:
        if full_reset:
            self._redis_client.flushdb()
            self._repository.clear()
            return
        for key in keys:
            self._redis_client.delete(key)
        self._repository.delete_many(keys)

    async def configure_memory(self, profile_key: str, max_memory_bytes: int) -> dict:
        self._redis_client.config_set_maxmemory(max_memory_bytes)
        return {
            "profile_key": profile_key,
            "max_memory_bytes": max_memory_bytes,
            "redis": self._redis_client.info_memory(),
        }

    async def seed(self, seed_input: SeedStateInput) -> None:
        documents = seed_input.documents
        if documents:
            self._repository.seed(documents)

        for key in documents:
            self._redis_client.delete(key)

        if seed_input.warm_cache:
            ttl_seconds = redis_ttl_for_request(seed_input.ttl_enabled, seed_input.ttl_seconds)
            for key, value in documents.items():
                self._redis_client.set(key, value)
                if ttl_seconds is not None:
                    self._redis_client.expire(key, ttl_seconds)

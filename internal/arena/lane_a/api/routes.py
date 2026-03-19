from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field, model_validator

from internal.arena.common.models import ArenaRequest
from internal.arena.common.models import SeedStateInput
from internal.arena.lane.cache_policy import redis_ttl_for_request

router = APIRouter()


class ExecutePayload(BaseModel):
    request_id: str = Field(min_length=1)
    mode: Literal["manual", "scenario"]
    command: Literal["SET", "GET", "DEL", "HSET", "HGET", "HGETALL"]
    key: str = Field(min_length=1)
    field: str | None = None
    value: str | None = None
    ttl_enabled: bool = False
    ttl_seconds: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_payload(self) -> "ExecutePayload":
        requires_field = self.command in {"HSET", "HGET"}
        requires_value = self.command in {"SET", "HSET"}
        if requires_field and not self.field:
            raise ValueError(f"{self.command} requires a field")
        if not requires_field:
            self.field = None
        if requires_value and self.value is None:
            raise ValueError(f"{self.command} requires a value")
        if not requires_value:
            self.value = None
        return self


class ResetPayload(BaseModel):
    keys: list[str] = Field(default_factory=list)
    full_reset: bool = False


class SeedPayload(BaseModel):
    documents: dict[str, str] = Field(default_factory=dict)
    warm_cache: bool = False
    ttl_enabled: bool = False
    ttl_seconds: float | None = Field(default=None, gt=0)


class MemoryConfigPayload(BaseModel):
    profile_key: str = Field(min_length=1)
    max_memory_bytes: int = Field(ge=0)


@router.post("/execute")
async def execute(payload: ExecutePayload, request: Request) -> dict:
    executor = request.app.state.executor
    request.app.state.known_keys.add(payload.key)
    result = await executor.execute(
        ArenaRequest(
            request_id=payload.request_id,
            mode=payload.mode,
            command=payload.command,
            key=payload.key,
            field=payload.field,
            value=payload.value,
            ttl_enabled=payload.ttl_enabled,
            ttl_seconds=payload.ttl_seconds,
        )
    )
    return result.to_dict()


@router.post("/reset")
async def reset_lane(payload: ResetPayload, request: Request) -> dict:
    executor = request.app.state.executor
    known_keys: set[str] = request.app.state.known_keys
    repository = request.app.state.repository
    redis_client = request.app.state.redis_client

    if payload.full_reset:
        repository.clear()
        redis_client.flushdb()
        known_keys.clear()
        return {"message": "Lane A full reset complete.", "deleted_keys": [], "full_reset": True}

    keys = payload.keys or list(known_keys)
    executor.clear(keys)
    for key in keys:
        known_keys.discard(key)
    return {"message": "Lane A reset complete.", "deleted_keys": keys, "full_reset": False}


@router.post("/seed")
async def seed_lane(payload: SeedPayload, request: Request) -> dict:
    repository = request.app.state.repository
    redis_client = request.app.state.redis_client
    known_keys: set[str] = request.app.state.known_keys

    documents = payload.documents
    if documents:
        repository.seed(documents)
        known_keys.update(documents.keys())

    for key in documents:
        redis_client.delete(key)

    if payload.warm_cache:
        ttl_seconds = redis_ttl_for_request(payload.ttl_enabled, payload.ttl_seconds)
        for key, value in documents.items():
            redis_client.set(key, value)
            if ttl_seconds is not None:
                redis_client.expire(key, ttl_seconds)

    return {
        "message": "Lane A seed complete.",
        "seeded_keys": list(documents.keys()),
        "warm_cache": payload.warm_cache,
    }


@router.post("/control/memory")
async def configure_memory(payload: MemoryConfigPayload, request: Request) -> dict:
    redis_client = request.app.state.redis_client
    redis_client.config_set_maxmemory(payload.max_memory_bytes)
    redis_stats = redis_client.info_memory()
    return {
        "message": "Lane A memory profile applied.",
        "profile_key": payload.profile_key,
        "max_memory_bytes": payload.max_memory_bytes,
        "redis": redis_stats,
    }


@router.get("/health")
async def health(request: Request) -> dict:
    repository = request.app.state.repository
    repository_settings = request.app.state.repository_settings
    redis_settings = request.app.state.redis_settings
    redis_client = request.app.state.redis_client
    mongo_health = repository.healthcheck()
    mongo_stats = repository.stats()
    redis_health = {
        "status": "ok",
        "backend": redis_settings.backend,
        "host": redis_settings.host,
        "port": redis_settings.port,
    }
    redis_stats = {
        "used_memory": 0,
        "maxmemory": 0,
        "keys": 0,
        "evicted_keys": 0,
    }
    try:
        redis_client.ping()
        redis_stats = redis_client.info_memory()
    except Exception as exc:
        redis_health["status"] = "error"
        redis_health["error"] = str(exc)

    status = "ok"
    if mongo_health.get("status") != "ok" or redis_health.get("status") != "ok":
        status = "degraded"
    return {
        "status": status,
        "lane": "redis_db",
        "redis": redis_health,
        "mongo": mongo_health,
        "redis_backend": redis_settings.backend,
        "redis_host": redis_settings.host,
        "redis_port": redis_settings.port,
        "mongo_backend": repository_settings.backend,
        "storage": {
            "redis": {
                "available": True,
                "logical_bytes": redis_stats.get("used_memory", 0),
                "key_count": redis_stats.get("keys", 0),
                "max_memory_bytes": redis_stats.get("maxmemory", 0),
                "evicted_keys": redis_stats.get("evicted_keys", 0),
            },
            "mongo": {
                "logical_bytes": mongo_stats.get("logical_bytes", 0),
                "document_count": mongo_stats.get("document_count", 0),
            },
        },
    }

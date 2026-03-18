from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from internal.arena.common.models import ArenaRequest
from internal.arena.common.models import SeedStateInput
from internal.arena.lane.cache_policy import redis_ttl_for_request

router = APIRouter()


class ExecutePayload(BaseModel):
    request_id: str = Field(min_length=1)
    mode: Literal["manual", "scenario"]
    command: Literal["SET", "GET", "DEL"]
    key: str = Field(min_length=1)
    value: str | None = None
    ttl_enabled: bool = False


class ResetPayload(BaseModel):
    keys: list[str] = Field(default_factory=list)


class SeedPayload(BaseModel):
    documents: dict[str, str] = Field(default_factory=dict)
    warm_cache: bool = False
    ttl_enabled: bool = False


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
            value=payload.value,
            ttl_enabled=payload.ttl_enabled,
        )
    )
    return result.to_dict()


@router.post("/reset")
async def reset_lane(payload: ResetPayload, request: Request) -> dict:
    executor = request.app.state.executor
    known_keys: set[str] = request.app.state.known_keys
    keys = payload.keys or list(known_keys)
    executor.clear(keys)
    for key in keys:
        known_keys.discard(key)
    return {"message": "Lane A reset complete.", "deleted_keys": keys}


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
        ttl_seconds = redis_ttl_for_request(payload.ttl_enabled)
        for key, value in documents.items():
            redis_client.set(key, value)
            if ttl_seconds is not None:
                redis_client.expire(key, ttl_seconds)

    return {
        "message": "Lane A seed complete.",
        "seeded_keys": list(documents.keys()),
        "warm_cache": payload.warm_cache,
    }


@router.get("/health")
async def health(request: Request) -> dict:
    repository = request.app.state.repository
    repository_settings = request.app.state.repository_settings
    redis_settings = request.app.state.redis_settings
    redis_client = request.app.state.redis_client
    mongo_health = repository.healthcheck()
    redis_health = {
        "status": "ok",
        "backend": redis_settings.backend,
        "host": redis_settings.host,
        "port": redis_settings.port,
    }
    if redis_settings.backend == "redis_py":
        probe_key = "__arena:health__"
        try:
            redis_client.set(probe_key, "ok")
            probe_value = redis_client.get(probe_key)
            redis_client.delete(probe_key)
            if probe_value != "ok":
                raise RuntimeError("unexpected probe value")
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
    }

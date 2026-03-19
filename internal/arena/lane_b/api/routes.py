from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field, model_validator

from internal.arena.common.models import ArenaRequest

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
    if payload.full_reset:
        repository.clear()
        known_keys.clear()
        return {"message": "Lane B full reset complete.", "deleted_keys": [], "full_reset": True}
    keys = payload.keys or list(known_keys)
    executor.clear(keys)
    for key in keys:
        known_keys.discard(key)
    return {"message": "Lane B reset complete.", "deleted_keys": keys, "full_reset": False}


@router.post("/seed")
async def seed_lane(payload: SeedPayload, request: Request) -> dict:
    repository = request.app.state.repository
    known_keys: set[str] = request.app.state.known_keys

    documents = payload.documents
    if documents:
        repository.seed(documents)
        known_keys.update(documents.keys())

    return {
        "message": "Lane B seed complete.",
        "seeded_keys": list(documents.keys()),
    }


@router.get("/health")
async def health(request: Request) -> dict:
    repository = request.app.state.repository
    repository_settings = request.app.state.repository_settings
    mongo_health = repository.healthcheck()
    mongo_stats = repository.stats()
    return {
        "status": "ok" if mongo_health.get("status") == "ok" else "degraded",
        "lane": "db_only",
        "mongo": mongo_health,
        "mongo_backend": repository_settings.backend,
        "storage": {
            "redis": {
                "available": False,
                "logical_bytes": 0,
                "key_count": 0,
                "max_memory_bytes": 0,
                "evicted_keys": 0,
            },
            "mongo": {
                "logical_bytes": mongo_stats.get("logical_bytes", 0),
                "document_count": mongo_stats.get("document_count", 0),
            },
        },
    }

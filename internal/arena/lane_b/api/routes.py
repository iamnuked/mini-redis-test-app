from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from internal.arena.common.models import ArenaRequest

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
    return {"message": "Lane B reset complete.", "deleted_keys": keys}


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
    return {
        "status": "ok" if mongo_health.get("status") == "ok" else "degraded",
        "lane": "db_only",
        "mongo": mongo_health,
        "mongo_backend": repository_settings.backend,
    }

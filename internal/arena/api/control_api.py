from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter()


class MemoryProfilePayload(BaseModel):
    profile_key: str = Field(min_length=1)


class TtlProfilePayload(BaseModel):
    profile_key: str | None = None


@router.post("/api/controls/memory-profile")
async def set_memory_profile(payload: MemoryProfilePayload, request: Request) -> dict:
    gateway_service = request.app.state.gateway_service
    try:
        return await gateway_service.set_memory_profile(payload.profile_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/api/controls/ttl-profile")
async def set_ttl_profile(payload: TtlProfilePayload, request: Request) -> dict:
    gateway_service = request.app.state.gateway_service
    try:
        return await gateway_service.set_ttl_profile(payload.profile_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field, model_validator

from internal.arena.gateway.models import ManualCommandInput

router = APIRouter()


class ManualCommandPayload(BaseModel):
    command: Literal["SET", "GET", "DEL"]
    key: str = Field(min_length=1)
    value: str | None = None
    ttl_enabled: bool = False

    @model_validator(mode="after")
    def validate_payload(self) -> "ManualCommandPayload":
        if self.command == "SET" and self.value is None:
            raise ValueError("SET requires a value")
        if self.command != "SET":
            self.value = None
        return self


@router.post("/api/manual-command")
async def run_manual_command(payload: ManualCommandPayload, request: Request) -> dict:
    gateway_service = request.app.state.gateway_service
    execution = await gateway_service.execute_manual_command(
        ManualCommandInput(
            command=payload.command,
            key=payload.key,
            value=payload.value,
            ttl_enabled=payload.ttl_enabled,
        )
    )
    return execution.to_dict()

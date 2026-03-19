from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field, model_validator

from internal.arena.gateway.models import ManualCommandInput

router = APIRouter()


class ManualCommandPayload(BaseModel):
    command: Literal["SET", "GET", "DEL", "HSET", "HGET", "HGETALL"]
    key: str = Field(min_length=1)
    field: str | None = None
    value: str | None = None
    ttl_enabled: bool = False

    @model_validator(mode="after")
    def validate_payload(self) -> "ManualCommandPayload":
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


@router.post("/api/manual-command")
async def run_manual_command(payload: ManualCommandPayload, request: Request) -> dict:
    gateway_service = request.app.state.gateway_service
    execution = await gateway_service.execute_manual_command(
        ManualCommandInput(
            command=payload.command,
            key=payload.key,
            field=payload.field,
            value=payload.value,
            ttl_enabled=payload.ttl_enabled,
        )
    )
    return execution.to_dict()

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from internal.arena.gateway.models import ScenarioRunInput

router = APIRouter()


class ScenarioRunPayload(BaseModel):
    scenario_id: Literal["read", "write", "mixed"] = "read"
    users: int = Field(default=4, ge=1)
    duration_seconds: int = Field(default=10, ge=1)
    read_hot_percent: Literal[0, 20, 40, 60, 80, 100] | None = None
    ttl_enabled: bool = True
    ttl_seconds: float | None = Field(default=None, gt=0)


@router.post("/api/scenarios/run")
async def run_scenario(payload: ScenarioRunPayload, request: Request) -> dict:
    scenario_runner = request.app.state.scenario_runner
    response = await scenario_runner.run(
        ScenarioRunInput(
            scenario_id=payload.scenario_id,
            users=payload.users,
            duration_seconds=payload.duration_seconds,
            read_hot_percent=payload.read_hot_percent,
            ttl_enabled=payload.ttl_enabled,
            ttl_seconds=payload.ttl_seconds,
        )
    )
    return response.to_dict()


@router.post("/api/scenarios/reset")
async def reset_scenarios(request: Request) -> dict:
    scenario_runner = request.app.state.scenario_runner
    response = await scenario_runner.reset()
    return response.to_dict()

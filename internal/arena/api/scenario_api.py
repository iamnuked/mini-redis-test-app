from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from internal.arena.gateway.models import ScenarioRunInput

router = APIRouter()


class ScenarioRunPayload(BaseModel):
    scenario_id: Literal["hot_key", "ttl_expiry"]
    users: int = Field(default=4, ge=1)
    duration_seconds: int = Field(default=10, ge=1)
    ttl_enabled: bool = False


@router.post("/api/scenarios/run")
async def run_scenario(payload: ScenarioRunPayload, request: Request) -> dict:
    scenario_runner = request.app.state.scenario_runner
    response = await scenario_runner.run(
        ScenarioRunInput(
            scenario_id=payload.scenario_id,
            users=payload.users,
            duration_seconds=payload.duration_seconds,
            ttl_enabled=payload.ttl_enabled,
        )
    )
    return response.to_dict()


@router.post("/api/scenarios/reset")
async def reset_scenarios(request: Request) -> dict:
    scenario_runner = request.app.state.scenario_runner
    response = await scenario_runner.reset()
    return response.to_dict()

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/api/health")
async def healthcheck(request: Request) -> dict:
    gateway_service = request.app.state.gateway_service
    scenario_runner = request.app.state.scenario_runner
    payload = await gateway_service.healthcheck()
    payload["scenario"] = scenario_runner.status()
    return payload

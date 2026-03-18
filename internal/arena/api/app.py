from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from internal.arena.api.events_api import router as events_router
from internal.arena.api.health_api import router as health_router
from internal.arena.api.manual_command_api import router as manual_command_router
from internal.arena.api.scenario_api import router as scenario_router
from internal.arena.events.bus import ArenaEventBus
from internal.arena.events.history import EventHistory
from internal.arena.gateway.lane_client import ArenaLaneClientSettings
from internal.arena.gateway.lane_client import ArenaLaneHttpClient
from internal.arena.gateway.service import ArenaGatewayService
from internal.arena.scenario.runner import ArenaScenarioRunner
import os


def create_app() -> FastAPI:
    app = FastAPI(title="mini-redis Arena", version="0.1.0")

    event_bus = ArenaEventBus()
    event_history = EventHistory()
    lane_timeout_seconds = float(os.getenv("ARENA_LANE_TIMEOUT_SECONDS", "5.0"))
    redis_lane_client = ArenaLaneHttpClient(
        settings=ArenaLaneClientSettings(
            name="lane-a",
            base_url=os.getenv("ARENA_LANE_A_BASE_URL", "http://127.0.0.1:8001"),
            timeout_seconds=lane_timeout_seconds,
        )
    )
    db_only_lane_client = ArenaLaneHttpClient(
        settings=ArenaLaneClientSettings(
            name="lane-b",
            base_url=os.getenv("ARENA_LANE_B_BASE_URL", "http://127.0.0.1:8002"),
            timeout_seconds=lane_timeout_seconds,
        )
    )

    gateway_service = ArenaGatewayService(
        redis_lane=redis_lane_client,
        db_only_lane=db_only_lane_client,
        event_bus=event_bus,
        event_history=event_history,
    )
    scenario_runner = ArenaScenarioRunner(
        gateway_service=gateway_service,
        event_history=event_history,
    )

    app.state.event_bus = event_bus
    app.state.event_history = event_history
    app.state.gateway_service = gateway_service
    app.state.redis_lane_client = redis_lane_client
    app.state.db_only_lane_client = db_only_lane_client
    app.state.scenario_runner = scenario_runner

    app.include_router(manual_command_router)
    app.include_router(scenario_router)
    app.include_router(events_router)
    app.include_router(health_router)

    static_dir = Path(__file__).resolve().parents[3] / "web" / "arena_dashboard"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="dashboard")

    return app

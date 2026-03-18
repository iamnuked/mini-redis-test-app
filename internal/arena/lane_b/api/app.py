from __future__ import annotations

from fastapi import FastAPI

from internal.arena.lane.db_only_adapter import DBOnlyLaneAdapter
from internal.arena.lane_b.api.routes import router as lane_b_router
from internal.arena.mongo.repository import MongoRepositorySettings
from internal.arena.mongo.repository import build_arena_repository


def create_app() -> FastAPI:
    app = FastAPI(title="Arena Lane B", version="0.1.0")

    repository_settings = MongoRepositorySettings.from_env(
        default_backend="pymongo",
        default_db_name="arena_lane_b",
    )
    repository = build_arena_repository(repository_settings)
    executor = DBOnlyLaneAdapter(repository=repository)

    app.state.executor = executor
    app.state.repository = repository
    app.state.repository_settings = repository_settings
    app.state.known_keys = set()

    app.include_router(lane_b_router)
    return app

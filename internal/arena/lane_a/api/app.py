from __future__ import annotations

from contextlib import asynccontextmanager
import os

from fastapi import FastAPI

from internal.arena.lane.redis_client import MiniRedisConnectionSettings
from internal.arena.lane.redis_client import build_mini_redis_client
from internal.arena.lane.redis_db_adapter import RedisDBLaneAdapter
from internal.arena.lane_a.api.routes import router as lane_a_router
from internal.arena.mongo.repository import MongoRepositorySettings
from internal.arena.mongo.repository import build_arena_repository


def create_app() -> FastAPI:
    redis_settings = MiniRedisConnectionSettings.from_env()
    if "ARENA_REDIS_BACKEND" not in os.environ:
        redis_settings.backend = "redis_py"
    repository_settings = MongoRepositorySettings.from_env(
        default_backend="pymongo",
        default_db_name="arena_lane_a",
    )
    redis_client = build_mini_redis_client(redis_settings)
    repository = build_arena_repository(repository_settings)
    executor = RedisDBLaneAdapter(redis_client=redis_client, repository=repository)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        redis_client.close()

    app = FastAPI(title="Arena Lane A", version="0.1.0", lifespan=lifespan)

    app.state.executor = executor
    app.state.repository = repository
    app.state.redis_client = redis_client
    app.state.repository_settings = repository_settings
    app.state.redis_settings = redis_settings
    app.state.known_keys = set()

    app.include_router(lane_a_router)
    return app

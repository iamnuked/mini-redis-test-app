from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


def _read_settings_file(path_value: str | None) -> dict[str, object]:
    if not path_value:
        return {}
    path = Path(path_value)
    if not path.is_file():
        raise FileNotFoundError(f"settings file not found: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("settings file must contain a JSON object")
    return raw


@dataclass(frozen=True)
class ControllerSettings:
    controller_host: str = "127.0.0.1"
    controller_port: int = 8000
    redis_host: str = "127.0.0.1"
    redis_port: int = 6379
    redis_timeout_seconds: float = 1.0
    baseline_backend: str = "mock"
    mongodb_uri: str = "mongodb://127.0.0.1:27017"
    mongodb_db_name: str = "mini_redis_benchmark"
    mongodb_collection: str = "detail_pages"
    mongodb_seed_file: str = "data/mongodb/detail_page_seed.json"
    mongodb_connect_timeout_ms: int = 1000

    @classmethod
    def from_env(cls) -> "ControllerSettings":
        file_values = _read_settings_file(os.getenv("APP_SETTINGS_FILE"))
        return cls(
            controller_host=os.getenv("BENCHMARK_CONTROLLER_HOST", str(file_values.get("controller_host", "127.0.0.1"))),
            controller_port=int(os.getenv("BENCHMARK_CONTROLLER_PORT", str(file_values.get("controller_port", "8000")))),
            redis_host=os.getenv("MINI_REDIS_HOST", str(file_values.get("redis_host", "127.0.0.1"))),
            redis_port=int(os.getenv("MINI_REDIS_PORT", str(file_values.get("redis_port", "6379")))),
            redis_timeout_seconds=float(
                os.getenv("MINI_REDIS_TIMEOUT_SECONDS", str(file_values.get("redis_timeout_seconds", "1.0")))
            ),
            baseline_backend=os.getenv("BASELINE_BACKEND", str(file_values.get("baseline_backend", "mock"))),
            mongodb_uri=os.getenv("MONGODB_URI", str(file_values.get("mongodb_uri", "mongodb://127.0.0.1:27017"))),
            mongodb_db_name=os.getenv("MONGODB_DB_NAME", str(file_values.get("mongodb_db_name", "mini_redis_benchmark"))),
            mongodb_collection=os.getenv(
                "MONGODB_COLLECTION",
                str(file_values.get("mongodb_collection", "detail_pages")),
            ),
            mongodb_seed_file=os.getenv(
                "MONGODB_SEED_FILE",
                str(file_values.get("mongodb_seed_file", "data/mongodb/detail_page_seed.json")),
            ),
            mongodb_connect_timeout_ms=int(
                os.getenv(
                    "MONGODB_CONNECT_TIMEOUT_MS",
                    str(file_values.get("mongodb_connect_timeout_ms", "1000")),
                )
            ),
        )

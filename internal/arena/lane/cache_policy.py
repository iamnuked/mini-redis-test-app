from __future__ import annotations

import os


def default_ttl_seconds() -> float:
    return float(os.getenv("ARENA_DEFAULT_TTL_SECONDS", "5"))


def redis_ttl_for_request(ttl_enabled: bool, ttl_seconds: float | None = None) -> float | None:
    if not ttl_enabled:
        return None
    if ttl_seconds is not None:
        return ttl_seconds
    return default_ttl_seconds()

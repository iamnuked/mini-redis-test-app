from __future__ import annotations

import os


def default_ttl_seconds() -> int:
    return int(os.getenv("ARENA_DEFAULT_TTL_SECONDS", "5"))


def redis_ttl_for_request(ttl_enabled: bool) -> int | None:
    if not ttl_enabled:
        return None
    return default_ttl_seconds()

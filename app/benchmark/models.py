from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


@dataclass
class RunConfig:
    scenario: str
    iteration_count: int
    concurrency: int
    hit_rate_buckets: list[int]
    ttl_seconds: int
    include_reference: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FlowEvent:
    event_id: str
    request_id: str
    timestamp: float
    mode: str
    event_type: str
    stage: str
    duration_ms: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RunSummary:
    db_avg_ms: float
    redis_avg_ms: float
    reference_avg_ms: float | None
    p95_db_ms: float
    p95_redis_ms: float
    p95_reference_ms: float | None
    speedup_ratio: float
    improvement_percent: float
    break_even_hit_rate: int | None
    cache_hit_rate: float
    db_only_count: int
    redis_hit_count: int
    redis_miss_count: int
    fallback_count: int
    error_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RunRecord:
    run_id: str
    status: str
    config: RunConfig
    created_at: str
    updated_at: str
    started_at: str | None = None
    finished_at: str | None = None
    summary: RunSummary | None = None
    error_message: str | None = None
    mini_redis_commit: str | None = None
    app_commit: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.summary is not None:
            payload["summary"] = self.summary.to_dict()
        return payload

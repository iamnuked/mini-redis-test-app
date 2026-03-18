from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

CommandName = Literal["SET", "GET", "DEL"]
LaneName = Literal["redis_db", "db_only"]
RequestMode = Literal["manual", "scenario"]
LaneStatus = Literal["ok", "error"]
ScenarioId = Literal["hot_key", "ttl_expiry"]


@dataclass
class ManualCommandInput:
    command: CommandName
    key: str
    value: str | None = None
    ttl_enabled: bool = False


@dataclass
class ArenaRequest:
    request_id: str
    mode: RequestMode
    command: CommandName
    key: str
    value: str | None = None
    ttl_enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ArenaRequest":
        return cls(
            request_id=payload["request_id"],
            mode=payload["mode"],
            command=payload["command"],
            key=payload["key"],
            value=payload.get("value"),
            ttl_enabled=bool(payload.get("ttl_enabled", False)),
        )


@dataclass
class CacheResult:
    hit: bool = False
    miss: bool = False

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "CacheResult":
        if payload is None:
            return cls()
        return cls(
            hit=bool(payload.get("hit", False)),
            miss=bool(payload.get("miss", False)),
        )


@dataclass
class LaneMetrics:
    service_time_ms: float = 0.0
    db_time_ms: float = 0.0
    redis_time_ms: float = 0.0
    started_at_ns: int = 0
    finished_at_ns: int = 0
    gateway_round_trip_ms: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "LaneMetrics":
        if payload is None:
            return cls()
        return cls(
            service_time_ms=float(payload.get("service_time_ms", 0.0)),
            db_time_ms=float(payload.get("db_time_ms", 0.0)),
            redis_time_ms=float(payload.get("redis_time_ms", 0.0)),
            started_at_ns=int(payload.get("started_at_ns", 0)),
            finished_at_ns=int(payload.get("finished_at_ns", 0)),
            gateway_round_trip_ms=(
                float(payload["gateway_round_trip_ms"])
                if payload.get("gateway_round_trip_ms") is not None
                else None
            ),
        )


@dataclass
class LaneResult:
    request_id: str
    lane: LaneName
    status: LaneStatus
    latency_ms: float
    answer_text: str | None = None
    answer_kind: str | None = None
    value_preview: str | None = None
    path: list[str] = field(default_factory=list)
    storage_changes: list[str] = field(default_factory=list)
    cache: CacheResult = field(default_factory=CacheResult)
    mongo_reads: int = 0
    metrics: LaneMetrics = field(default_factory=LaneMetrics)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "LaneResult":
        metrics = LaneMetrics.from_dict(payload.get("metrics"))
        latency_ms = float(payload.get("latency_ms", metrics.service_time_ms))
        if metrics.service_time_ms == 0.0:
            metrics.service_time_ms = latency_ms
        return cls(
            request_id=payload["request_id"],
            lane=payload["lane"],
            status=payload["status"],
            latency_ms=latency_ms,
            answer_text=payload.get("answer_text"),
            answer_kind=payload.get("answer_kind"),
            value_preview=payload.get("value_preview"),
            path=list(payload.get("path", [])),
            storage_changes=list(payload.get("storage_changes", [])),
            cache=CacheResult.from_dict(payload.get("cache")),
            mongo_reads=int(payload.get("mongo_reads", 0)),
            metrics=metrics,
        )


@dataclass
class ExecutionSummary:
    faster_lane: LaneName | None = None
    latency_gap_ms: float | None = None
    fewer_mongo_reads_lane: LaneName | None = None
    mongo_read_gap: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExecutionResult:
    request: ArenaRequest
    redis_db: LaneResult
    db_only: LaneResult
    summary: ExecutionSummary

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ScenarioRunInput:
    scenario_id: ScenarioId
    users: int
    duration_seconds: int
    ttl_enabled: bool = False


@dataclass
class MessageResponse:
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EventEnvelope:
    type: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ResetStateInput:
    keys: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SeedStateInput:
    documents: dict[str, str] = field(default_factory=dict)
    warm_cache: bool = False
    ttl_enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

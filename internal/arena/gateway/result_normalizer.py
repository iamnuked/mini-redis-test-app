from __future__ import annotations

from internal.arena.gateway.models import (
    ArenaRequest,
    ExecutionResult,
    ExecutionSummary,
    LaneResult,
)


def build_summary(redis_result: LaneResult, db_only_result: LaneResult) -> ExecutionSummary:
    redis_latency_ms = redis_result.metrics.service_time_ms or redis_result.latency_ms
    db_only_latency_ms = db_only_result.metrics.service_time_ms or db_only_result.latency_ms

    faster_lane = None
    if redis_latency_ms < db_only_latency_ms:
        faster_lane = "redis_db"
    elif db_only_latency_ms < redis_latency_ms:
        faster_lane = "db_only"

    fewer_mongo_reads_lane = None
    if redis_result.mongo_reads < db_only_result.mongo_reads:
        fewer_mongo_reads_lane = "redis_db"
    elif db_only_result.mongo_reads < redis_result.mongo_reads:
        fewer_mongo_reads_lane = "db_only"

    return ExecutionSummary(
        faster_lane=faster_lane,
        latency_gap_ms=round(abs(redis_latency_ms - db_only_latency_ms), 3),
        fewer_mongo_reads_lane=fewer_mongo_reads_lane,
        mongo_read_gap=abs(redis_result.mongo_reads - db_only_result.mongo_reads),
    )


def build_execution(
    request: ArenaRequest,
    redis_result: LaneResult,
    db_only_result: LaneResult,
) -> ExecutionResult:
    return ExecutionResult(
        request=request,
        redis_db=redis_result,
        db_only=db_only_result,
        summary=build_summary(redis_result, db_only_result),
    )

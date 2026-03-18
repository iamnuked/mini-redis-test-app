from __future__ import annotations

from typing import Any

from app.api.timeline import build_request_timelines
from app.benchmark.models import RunRecord


def build_presentation_payload(record: RunRecord, events: list[dict[str, Any]]) -> dict[str, Any]:
    request_timelines = build_request_timelines(events)
    summary = record.summary.to_dict() if record.summary is not None else None

    cache_requests = [request for request in request_timelines if request["mode"] == "cache_aside"]
    hit_requests = [request for request in cache_requests if request["cache_status"] == "hit"]
    miss_requests = [
        request for request in cache_requests if request["cache_status"] in {"miss", "miss_writeback_failed"}
    ]

    return {
        "run_id": record.run_id,
        "status": record.status,
        "scenario": record.config.scenario,
        "config": record.config.to_dict(),
        "kpis": _build_kpis(summary, hit_requests, miss_requests),
        "lane_summary": _build_lane_summary(summary, request_timelines),
        "chart_series": _build_chart_series(summary, request_timelines),
    }


def _build_kpis(
    summary: dict[str, Any] | None,
    hit_requests: list[dict[str, Any]],
    miss_requests: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if summary is None:
        return None
    return {
        "db_avg_ms": float(summary["db_avg_ms"]),
        "redis_avg_ms": float(summary["redis_avg_ms"]),
        "redis_hit_avg_ms": _average_duration(hit_requests),
        "redis_miss_avg_ms": _average_duration(miss_requests),
        "reference_avg_ms": _optional_float(summary.get("reference_avg_ms")),
        "speedup_ratio": float(summary["speedup_ratio"]),
        "improvement_percent": float(summary["improvement_percent"]),
        "break_even_hit_rate": summary.get("break_even_hit_rate"),
        "cache_hit_rate": float(summary["cache_hit_rate"]),
        "error_count": int(summary["error_count"]),
    }


def _build_lane_summary(summary: dict[str, Any] | None, request_timelines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = {
        "db_only": [],
        "cache_aside": [],
        "redis_only_reference": [],
    }
    for request in request_timelines:
        grouped.setdefault(str(request["mode"]), []).append(request)

    items: list[dict[str, Any]] = []
    labels = {
        "db_only": "DB Only",
        "cache_aside": "Redis + DB",
        "redis_only_reference": "Redis Only Reference",
    }
    for mode in ("db_only", "cache_aside", "redis_only_reference"):
        requests = grouped.get(mode, [])
        if not requests and mode == "redis_only_reference" and not (summary and summary.get("reference_avg_ms") is not None):
            continue
        items.append(
            {
                "mode": mode,
                "label": labels[mode],
                "request_count": len(requests),
                "avg_duration_ms": _average_duration(requests),
                "hit_count": _count_cache_status(requests, "hit") + _count_cache_status(requests, "reference_hit"),
                "miss_count": _count_cache_status(requests, "miss") + _count_cache_status(requests, "miss_writeback_failed"),
                "fallback_count": _count_cache_status(requests, "fallback"),
                "error_count": sum(1 for request in requests if request["has_error"]),
            }
        )
    return items


def _build_chart_series(summary: dict[str, Any] | None, request_timelines: list[dict[str, Any]]) -> dict[str, Any]:
    cache_requests = [request for request in request_timelines if request["mode"] == "cache_aside"]
    hit_requests = [request for request in cache_requests if request["cache_status"] == "hit"]
    miss_requests = [
        request for request in cache_requests if request["cache_status"] in {"miss", "miss_writeback_failed"}
    ]
    reference_requests = [request for request in request_timelines if request["mode"] == "redis_only_reference"]

    latency_comparison: list[dict[str, Any]] = []
    if summary is not None:
        latency_comparison.append({"label": "DB Only Avg", "value": float(summary["db_avg_ms"])})
    hit_avg = _average_duration(hit_requests)
    miss_avg = _average_duration(miss_requests)
    if hit_avg is not None:
        latency_comparison.append({"label": "Redis Hit Avg", "value": hit_avg})
    if miss_avg is not None:
        latency_comparison.append({"label": "Redis Miss Avg", "value": miss_avg})
    if summary is not None:
        if hit_avg is None:
            latency_comparison.append({"label": "Redis + DB Avg", "value": float(summary["redis_avg_ms"])})
        if summary.get("reference_avg_ms") is not None:
            latency_comparison.append({"label": "Redis Only Avg", "value": float(summary["reference_avg_ms"])})

    path_ratio = [
        {"label": "DB Only", "value": sum(1 for request in request_timelines if request["mode"] == "db_only")},
        {"label": "Redis Hit", "value": len(hit_requests)},
        {"label": "Redis Miss", "value": len(miss_requests)},
        {"label": "Redis Reference", "value": len(reference_requests)},
        {"label": "Fallback", "value": sum(1 for request in request_timelines if request["cache_status"] == "fallback")},
        {"label": "Error", "value": sum(1 for request in request_timelines if request["has_error"])},
    ]

    stage_totals: dict[str, float] = {}
    for request in request_timelines:
        for stage, duration in request["stage_durations"].items():
            stage_totals[stage] = round(stage_totals.get(stage, 0.0) + float(duration), 2)
    timeline_stage_totals = [{"label": stage, "value": duration} for stage, duration in stage_totals.items()]

    return {
        "latency_comparison": latency_comparison,
        "path_ratio": path_ratio,
        "timeline_stage_totals": timeline_stage_totals,
    }


def _average_duration(requests: list[dict[str, Any]]) -> float | None:
    if not requests:
        return None
    total = sum(float(request["total_duration_ms"]) for request in requests)
    return round(total / len(requests), 2)


def _count_cache_status(requests: list[dict[str, Any]], status: str) -> int:
    return sum(1 for request in requests if request["cache_status"] == status)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)

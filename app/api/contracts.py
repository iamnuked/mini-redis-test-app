from __future__ import annotations

from typing import Any

from app.benchmark.models import FlowEvent, RunRecord


def serialize_run_list_item(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": payload["run_id"],
        "status": payload["status"],
        "scenario": payload["config"]["scenario"],
        "created_at": payload["created_at"],
        "updated_at": payload["updated_at"],
    }


def serialize_run_detail(record: RunRecord, logs: list[dict[str, Any]]) -> dict[str, Any]:
    payload = record.to_dict()
    payload["logs"] = [normalize_log_entry(entry) for entry in logs]
    return payload


def serialize_events_response(run_id: str, events: list[dict[str, Any] | FlowEvent]) -> dict[str, Any]:
    normalized_events: list[dict[str, Any]] = []
    for event in events:
        normalized_events.append(normalize_event_entry(event.to_dict() if isinstance(event, FlowEvent) else event))
    return {
        "run_id": run_id,
        "events": normalized_events,
    }


def serialize_requests_response(run_id: str, requests: list[dict[str, Any]]) -> dict[str, Any]:
    normalized_requests: list[dict[str, Any]] = []
    for request in requests:
        normalized_requests.append(
            {
                "request_id": str(request["request_id"]),
                "mode": str(request["mode"]),
                "started_at_ms": float(request["started_at_ms"]),
                "finished_at_ms": float(request["finished_at_ms"]),
                "total_duration_ms": float(request["total_duration_ms"]),
                "cache_status": str(request["cache_status"]),
                "path_summary": str(request["path_summary"]),
                "has_error": bool(request["has_error"]),
                "stage_durations": {
                    str(stage): float(duration)
                    for stage, duration in dict(request.get("stage_durations") or {}).items()
                },
                "event_count": int(request["event_count"]),
                "events": [
                    normalize_event_entry(event)
                    for event in list(request.get("events") or [])
                ],
            }
        )
    return {
        "run_id": run_id,
        "requests": normalized_requests,
    }


def serialize_presentation_response(payload: dict[str, Any]) -> dict[str, Any]:
    kpis = payload.get("kpis")
    normalized_kpis = None
    if kpis is not None:
        normalized_kpis = {
            "db_avg_ms": float(kpis["db_avg_ms"]),
            "redis_avg_ms": float(kpis["redis_avg_ms"]),
            "redis_hit_avg_ms": _optional_float(kpis.get("redis_hit_avg_ms")),
            "redis_miss_avg_ms": _optional_float(kpis.get("redis_miss_avg_ms")),
            "reference_avg_ms": _optional_float(kpis.get("reference_avg_ms")),
            "speedup_ratio": float(kpis["speedup_ratio"]),
            "improvement_percent": float(kpis["improvement_percent"]),
            "break_even_hit_rate": kpis.get("break_even_hit_rate"),
            "cache_hit_rate": float(kpis["cache_hit_rate"]),
            "error_count": int(kpis["error_count"]),
        }

    return {
        "run_id": str(payload["run_id"]),
        "status": str(payload["status"]),
        "scenario": str(payload["scenario"]),
        "config": dict(payload["config"]),
        "kpis": normalized_kpis,
        "lane_summary": [
            {
                "mode": str(item["mode"]),
                "label": str(item["label"]),
                "request_count": int(item["request_count"]),
                "avg_duration_ms": _optional_float(item.get("avg_duration_ms")),
                "hit_count": int(item["hit_count"]),
                "miss_count": int(item["miss_count"]),
                "fallback_count": int(item["fallback_count"]),
                "error_count": int(item["error_count"]),
            }
            for item in list(payload.get("lane_summary") or [])
        ],
        "chart_series": {
            "latency_comparison": [
                {"label": str(item["label"]), "value": float(item["value"])}
                for item in list(payload.get("chart_series", {}).get("latency_comparison") or [])
            ],
            "path_ratio": [
                {"label": str(item["label"]), "value": int(item["value"])}
                for item in list(payload.get("chart_series", {}).get("path_ratio") or [])
            ],
            "timeline_stage_totals": [
                {"label": str(item["label"]), "value": float(item["value"])}
                for item in list(payload.get("chart_series", {}).get("timeline_stage_totals") or [])
            ],
        },
    }


def normalize_log_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "timestamp": float(entry["timestamp"]),
        "level": str(entry["level"]),
        "stage": str(entry["stage"]),
        "message": str(entry["message"]),
        "metadata": dict(entry.get("metadata") or {}),
    }


def normalize_event_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_id": str(entry["event_id"]),
        "request_id": str(entry["request_id"]),
        "timestamp": float(entry["timestamp"]),
        "mode": str(entry["mode"]),
        "event_type": str(entry["event_type"]),
        "stage": str(entry["stage"]),
        "duration_ms": float(entry["duration_ms"]),
        "metadata": dict(entry.get("metadata") or {}),
    }


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)

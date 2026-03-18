from __future__ import annotations

from typing import Any

from app.api.contracts import normalize_event_entry


def build_request_timelines(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []

    for raw_event in events:
        event = normalize_event_entry(raw_event)
        request_id = event["request_id"]
        if request_id not in grouped:
            grouped[request_id] = []
            order.append(request_id)
        grouped[request_id].append(event)

    return [build_request_timeline(request_id, grouped[request_id]) for request_id in order]


def build_request_timeline(request_id: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    ordered_events = sorted(events, key=_event_sort_key)
    first_event = ordered_events[0]
    last_event = ordered_events[-1]
    mode = first_event["mode"]
    stage_durations = _aggregate_stage_durations(ordered_events)
    cache_status = _infer_cache_status(ordered_events)
    has_error = any(event["event_type"] == "error" for event in ordered_events)
    started_at_ms = float(first_event["timestamp"])
    finished_at_ms = float(last_event["timestamp"])
    total_duration_ms = _infer_total_duration_ms(ordered_events, finished_at_ms)

    return {
        "request_id": request_id,
        "mode": mode,
        "started_at_ms": started_at_ms,
        "finished_at_ms": finished_at_ms,
        "total_duration_ms": total_duration_ms,
        "cache_status": cache_status,
        "path_summary": _build_path_summary(mode, cache_status, has_error),
        "has_error": has_error,
        "stage_durations": stage_durations,
        "event_count": len(ordered_events),
        "events": ordered_events,
    }


def _aggregate_stage_durations(events: list[dict[str, Any]]) -> dict[str, float]:
    durations: dict[str, float] = {}
    for event in events:
        stage = str(event["stage"])
        durations[stage] = round(durations.get(stage, 0.0) + float(event["duration_ms"]), 2)
    return durations


def _infer_cache_status(events: list[dict[str, Any]]) -> str:
    response_event = next((event for event in reversed(events) if event["event_type"] == "response_sent"), None)
    if response_event is not None:
        metadata = response_event.get("metadata", {})
        cache_status = metadata.get("cache_status")
        if cache_status:
            return str(cache_status)

    event_types = {str(event["event_type"]) for event in events}
    if "cache_hit" in event_types:
        return "hit"
    if "cache_miss" in event_types:
        return "miss"
    if "fallback_used" in event_types:
        return "fallback"
    if "error" in event_types:
        return "error"
    if any(str(event["mode"]) == "redis_only_reference" for event in events):
        return "reference_hit"
    return "db_only"


def _infer_total_duration_ms(events: list[dict[str, Any]], finished_at_ms: float) -> float:
    response_event = next((event for event in reversed(events) if event["event_type"] == "response_sent"), None)
    if response_event is not None:
        total_duration = response_event.get("metadata", {}).get("total_duration_ms")
        if total_duration is not None:
            return round(float(total_duration), 2)
    return round(finished_at_ms, 2)


def _build_path_summary(mode: str, cache_status: str, has_error: bool) -> str:
    if mode == "db_only":
        return "App -> DB -> Response"
    if mode == "redis_only_reference":
        return "App -> Redis -> Response"
    if has_error and cache_status in {"fallback", "miss_writeback_failed"}:
        return "App -> Redis -> DB -> Response"
    if cache_status == "hit":
        return "App -> Redis -> Response"
    if cache_status in {"miss", "miss_writeback_failed"}:
        return "App -> Redis -> DB -> Redis -> Response"
    if cache_status == "fallback":
        return "App -> Redis -> DB -> Response"
    return "App -> Redis -> DB -> Response"


def _event_sort_key(event: dict[str, Any]) -> tuple[float, str]:
    return float(event["timestamp"]), str(event["event_id"])

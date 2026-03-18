from __future__ import annotations

from typing import Any

DEFAULT_HIT_RATE_BUCKETS = list(range(0, 101, 10))

SCENARIOS: list[dict[str, Any]] = [
    {
        "scenario_id": "detail_page",
        "title": "상세 페이지",
        "subtitle": "게시글 상세를 반복 조회하며 DB 전용과 Redis + DB를 비교합니다.",
        "description": "캐시 hit/miss 차이와 TTL 조건을 가장 직관적으로 설명하는 기본 시나리오입니다.",
        "tags": ["피드 화면", "검색 부하", "웜 캐시 비교"],
        "default_iteration_count": 10,
        "default_concurrency": 1,
        "default_ttl_seconds": 30,
        "default_hit_rate_buckets": DEFAULT_HIT_RATE_BUCKETS,
        "supported_cache_modes": ["cold", "warm", "mixed"],
        "supported_data_scales": ["small", "medium", "large"],
    },
    {
        "scenario_id": "search_autocomplete",
        "title": "검색 자동완성",
        "subtitle": "짧은 키 반복 조회를 통해 캐시 적중률과 응답 안정성을 비교합니다.",
        "description": "짧은 요청이 많이 들어오는 상황에서 Redis 적중률이 응답 꼬리를 얼마나 줄이는지 확인합니다.",
        "tags": ["검색 부하", "짧은 응답", "혼합 캐시"],
        "default_iteration_count": 30,
        "default_concurrency": 1,
        "default_ttl_seconds": 15,
        "default_hit_rate_buckets": DEFAULT_HIT_RATE_BUCKETS,
        "supported_cache_modes": ["cold", "warm", "mixed"],
        "supported_data_scales": ["small", "medium"],
    },
]


def list_scenarios() -> list[dict[str, Any]]:
    return [scenario.copy() for scenario in SCENARIOS]


def get_scenario(scenario_id: str) -> dict[str, Any] | None:
    return next((scenario.copy() for scenario in SCENARIOS if scenario["scenario_id"] == scenario_id), None)


def default_demo_config() -> dict[str, Any]:
    return {
        "data_scales": [
            {"id": "small", "label": "1천 건", "iteration_count": 10},
            {"id": "medium", "label": "1만 건", "iteration_count": 100},
            {"id": "large", "label": "10만 건", "iteration_count": 1000},
        ],
        "cache_modes": [
            {"id": "cold", "label": "콜드 캐시"},
            {"id": "warm", "label": "웜 캐시"},
            {"id": "mixed", "label": "혼합 캐시"},
        ],
        "key_patterns": [
            {"id": "same_key", "label": "동일 키"},
            {"id": "random_key", "label": "랜덤 키"},
        ],
    }

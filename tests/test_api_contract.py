from __future__ import annotations

import unittest

from app.api.contracts import (
    normalize_event_entry,
    normalize_log_entry,
    serialize_events_response,
    serialize_presentation_response,
    serialize_requests_response,
    serialize_run_detail,
    serialize_run_list_item,
)
from app.benchmark.models import FlowEvent, RunConfig, RunRecord, RunSummary, utc_now_iso


class ApiContractTest(unittest.TestCase):
    def test_serialize_run_list_item_keeps_expected_keys(self) -> None:
        payload = {
            "run_id": "run_1",
            "status": "completed",
            "config": {"scenario": "detail_page"},
            "created_at": "2026-03-18T12:30:00Z",
            "updated_at": "2026-03-18T12:30:04Z",
        }

        item = serialize_run_list_item(payload)

        self.assertEqual(
            set(item.keys()),
            {"run_id", "status", "scenario", "created_at", "updated_at"},
        )
        self.assertEqual(item["scenario"], "detail_page")

    def test_serialize_run_detail_normalizes_logs(self) -> None:
        now = utc_now_iso()
        record = RunRecord(
            run_id="run_detail",
            status="completed",
            config=RunConfig("detail_page", 10, 1, [0, 50, 100], 30, True),
            created_at=now,
            updated_at=now,
            started_at=now,
            finished_at=now,
            summary=RunSummary(
                db_avg_ms=100.0,
                redis_avg_ms=25.0,
                reference_avg_ms=10.0,
                p95_db_ms=120.0,
                p95_redis_ms=30.0,
                p95_reference_ms=12.0,
                speedup_ratio=4.0,
                improvement_percent=75.0,
                break_even_hit_rate=50,
                cache_hit_rate=60.0,
                db_only_count=10,
                redis_hit_count=6,
                redis_miss_count=4,
                fallback_count=1,
                error_count=1,
            ),
        )

        payload = serialize_run_detail(
            record,
            [{"timestamp": 1773832200, "level": "INFO", "stage": "bootstrap", "message": "queued"}],
        )

        self.assertIn("summary", payload)
        self.assertEqual(payload["logs"][0]["metadata"], {})
        self.assertEqual(payload["summary"]["redis_hit_count"], 6)

    def test_serialize_events_response_normalizes_numbers_and_metadata(self) -> None:
        event = FlowEvent(
            event_id="evt_1",
            request_id="req_1",
            timestamp=1,
            mode="cache_aside",
            event_type="cache_hit",
            stage="redis_lookup",
            duration_ms=2,
            metadata={"bucket": 50},
        )

        payload = serialize_events_response("run_1", [event, {"event_id": "evt_2", "request_id": "req_2", "timestamp": 3, "mode": "db_only", "event_type": "response_sent", "stage": "response", "duration_ms": 0}])

        self.assertEqual(payload["run_id"], "run_1")
        self.assertEqual(len(payload["events"]), 2)
        self.assertEqual(payload["events"][0]["metadata"]["bucket"], 50)
        self.assertEqual(payload["events"][1]["metadata"], {})
        self.assertIsInstance(payload["events"][0]["timestamp"], float)

    def test_normalize_helpers_fill_missing_metadata(self) -> None:
        log = normalize_log_entry(
            {"timestamp": 1773832200, "level": "INFO", "stage": "aggregation", "message": "done"}
        )
        event = normalize_event_entry(
            {
                "event_id": "evt_3",
                "request_id": "req_3",
                "timestamp": 4,
                "mode": "db_only",
                "event_type": "response_sent",
                "stage": "response",
                "duration_ms": 0,
            }
        )

        self.assertEqual(log["metadata"], {})
        self.assertEqual(event["metadata"], {})

    def test_serialize_requests_response_normalizes_timeline_shape(self) -> None:
        payload = serialize_requests_response(
            "run_1",
            [
                {
                    "request_id": "cache-1",
                    "mode": "cache_aside",
                    "started_at_ms": 0,
                    "finished_at_ms": 21.2,
                    "total_duration_ms": 21.2,
                    "cache_status": "miss",
                    "path_summary": "App -> Redis -> DB -> Redis -> Response",
                    "has_error": False,
                    "stage_durations": {"redis_lookup": 2.31},
                    "event_count": 2,
                    "events": [
                        {
                            "event_id": "evt_1",
                            "request_id": "cache-1",
                            "timestamp": 0,
                            "mode": "cache_aside",
                            "event_type": "request_started",
                            "stage": "request",
                            "duration_ms": 0,
                        }
                    ],
                }
            ],
        )

        request = payload["requests"][0]
        self.assertEqual(payload["run_id"], "run_1")
        self.assertEqual(request["cache_status"], "miss")
        self.assertEqual(request["stage_durations"]["redis_lookup"], 2.31)
        self.assertEqual(request["events"][0]["metadata"], {})

    def test_serialize_presentation_response_normalizes_dashboard_shape(self) -> None:
        payload = serialize_presentation_response(
            {
                "run_id": "run_1",
                "status": "completed",
                "scenario": "detail_page",
                "config": {"iteration_count": 10},
                "kpis": {
                    "db_avg_ms": 100,
                    "redis_avg_ms": 25,
                    "redis_hit_avg_ms": 12,
                    "redis_miss_avg_ms": 42,
                    "reference_avg_ms": None,
                    "speedup_ratio": 4,
                    "improvement_percent": 75,
                    "break_even_hit_rate": 50,
                    "cache_hit_rate": 60,
                    "error_count": 1,
                },
                "lane_summary": [
                    {
                        "mode": "cache_aside",
                        "label": "Redis + DB",
                        "request_count": 10,
                        "avg_duration_ms": 25,
                        "hit_count": 6,
                        "miss_count": 4,
                        "fallback_count": 1,
                        "error_count": 1,
                    }
                ],
                "chart_series": {
                    "latency_comparison": [{"label": "DB Only Avg", "value": 100}],
                    "path_ratio": [{"label": "Redis Hit", "value": 6}],
                    "timeline_stage_totals": [{"label": "db_lookup", "value": 60}],
                },
            }
        )

        self.assertEqual(payload["run_id"], "run_1")
        self.assertEqual(payload["lane_summary"][0]["avg_duration_ms"], 25.0)
        self.assertEqual(payload["chart_series"]["path_ratio"][0]["value"], 6)
        self.assertEqual(payload["kpis"]["db_avg_ms"], 100.0)
        self.assertEqual(payload["kpis"]["redis_hit_avg_ms"], 12.0)
        self.assertEqual(payload["kpis"]["redis_miss_avg_ms"], 42.0)


if __name__ == "__main__":
    unittest.main()

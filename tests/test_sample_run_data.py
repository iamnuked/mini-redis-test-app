from __future__ import annotations

import json
import unittest
from pathlib import Path


class SampleRunDataTest(unittest.TestCase):
    def test_sample_run_detail_contains_required_contract_fields(self) -> None:
        payload = json.loads(Path("docs/samples/sample-run-completed.json").read_text(encoding="utf-8"))

        self.assertEqual(
            set(payload.keys()),
            {
                "run_id",
                "status",
                "config",
                "created_at",
                "updated_at",
                "started_at",
                "finished_at",
                "summary",
                "error_message",
                "mini_redis_commit",
                "app_commit",
                "logs",
            },
        )
        self.assertIn("redis_hit_count", payload["summary"])
        self.assertIsInstance(payload["logs"], list)
        self.assertEqual(payload["logs"][0]["metadata"], {})

    def test_sample_event_stream_contains_required_contract_fields(self) -> None:
        payload = json.loads(Path("docs/samples/sample-run-events.json").read_text(encoding="utf-8"))

        self.assertEqual(set(payload.keys()), {"run_id", "events"})
        self.assertGreater(len(payload["events"]), 0)
        first = payload["events"][0]
        self.assertEqual(
            set(first.keys()),
            {
                "event_id",
                "request_id",
                "timestamp",
                "mode",
                "event_type",
                "stage",
                "duration_ms",
                "metadata",
            },
        )
        self.assertIsInstance(first["metadata"], dict)

    def test_sample_request_timeline_contains_required_contract_fields(self) -> None:
        payload = json.loads(Path("docs/samples/sample-run-requests.json").read_text(encoding="utf-8"))

        self.assertEqual(set(payload.keys()), {"run_id", "requests"})
        self.assertGreater(len(payload["requests"]), 0)
        first = payload["requests"][0]
        self.assertEqual(
            set(first.keys()),
            {
                "request_id",
                "mode",
                "started_at_ms",
                "finished_at_ms",
                "total_duration_ms",
                "cache_status",
                "path_summary",
                "has_error",
                "stage_durations",
                "event_count",
                "events",
            },
        )
        self.assertIsInstance(first["stage_durations"], dict)
        self.assertIsInstance(first["events"], list)

    def test_sample_presentation_contains_required_contract_fields(self) -> None:
        payload = json.loads(Path("docs/samples/sample-run-presentation.json").read_text(encoding="utf-8"))

        self.assertEqual(
            set(payload.keys()),
            {"run_id", "status", "scenario", "config", "kpis", "lane_summary", "chart_series"},
        )
        self.assertIn("db_avg_ms", payload["kpis"])
        self.assertIn("redis_hit_avg_ms", payload["kpis"])
        self.assertIn("redis_miss_avg_ms", payload["kpis"])
        self.assertIsInstance(payload["lane_summary"], list)
        self.assertEqual(
            set(payload["chart_series"].keys()),
            {"latency_comparison", "path_ratio", "timeline_stage_totals"},
        )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from app.api.timeline import build_request_timelines


class RequestTimelineTest(unittest.TestCase):
    def test_build_request_timelines_groups_requests_and_computes_path_summary(self) -> None:
        timelines = build_request_timelines(
            [
                {
                    "event_id": "cache-1-start",
                    "request_id": "cache-1",
                    "timestamp": 0,
                    "mode": "cache_aside",
                    "event_type": "request_started",
                    "stage": "request",
                    "duration_ms": 0,
                    "metadata": {},
                },
                {
                    "event_id": "cache-1-miss",
                    "request_id": "cache-1",
                    "timestamp": 2.0,
                    "mode": "cache_aside",
                    "event_type": "cache_miss",
                    "stage": "redis_lookup",
                    "duration_ms": 2.0,
                    "metadata": {},
                },
                {
                    "event_id": "cache-1-db-finish",
                    "request_id": "cache-1",
                    "timestamp": 18.0,
                    "mode": "cache_aside",
                    "event_type": "db_query_completed",
                    "stage": "db_lookup",
                    "duration_ms": 16.0,
                    "metadata": {},
                },
                {
                    "event_id": "cache-1-cache-set",
                    "request_id": "cache-1",
                    "timestamp": 21.0,
                    "mode": "cache_aside",
                    "event_type": "cache_set",
                    "stage": "writeback",
                    "duration_ms": 3.0,
                    "metadata": {},
                },
                {
                    "event_id": "cache-1-response",
                    "request_id": "cache-1",
                    "timestamp": 21.0,
                    "mode": "cache_aside",
                    "event_type": "response_sent",
                    "stage": "response",
                    "duration_ms": 0,
                    "metadata": {"total_duration_ms": 21.0, "cache_status": "miss"},
                },
            ]
        )

        self.assertEqual(len(timelines), 1)
        timeline = timelines[0]
        self.assertEqual(timeline["request_id"], "cache-1")
        self.assertEqual(timeline["cache_status"], "miss")
        self.assertEqual(timeline["path_summary"], "App -> Redis -> DB -> Redis -> Response")
        self.assertEqual(timeline["stage_durations"]["db_lookup"], 16.0)
        self.assertEqual(timeline["total_duration_ms"], 21.0)

    def test_build_request_timelines_handles_fallback_and_error(self) -> None:
        timelines = build_request_timelines(
            [
                {
                    "event_id": "cache-2-start",
                    "request_id": "cache-2",
                    "timestamp": 0,
                    "mode": "cache_aside",
                    "event_type": "request_started",
                    "stage": "request",
                    "duration_ms": 0,
                    "metadata": {},
                },
                {
                    "event_id": "cache-2-fallback",
                    "request_id": "cache-2",
                    "timestamp": 1.5,
                    "mode": "cache_aside",
                    "event_type": "fallback_used",
                    "stage": "redis_lookup",
                    "duration_ms": 1.5,
                    "metadata": {},
                },
                {
                    "event_id": "cache-2-error",
                    "request_id": "cache-2",
                    "timestamp": 1.5,
                    "mode": "cache_aside",
                    "event_type": "error",
                    "stage": "redis_lookup",
                    "duration_ms": 0,
                    "metadata": {},
                },
                {
                    "event_id": "cache-2-response",
                    "request_id": "cache-2",
                    "timestamp": 19.0,
                    "mode": "cache_aside",
                    "event_type": "response_sent",
                    "stage": "response",
                    "duration_ms": 0,
                    "metadata": {"total_duration_ms": 19.0, "cache_status": "fallback"},
                },
            ]
        )

        timeline = timelines[0]
        self.assertTrue(timeline["has_error"])
        self.assertEqual(timeline["cache_status"], "fallback")
        self.assertEqual(timeline["path_summary"], "App -> Redis -> DB -> Response")

    def test_build_request_timelines_handles_db_only_and_reference_modes(self) -> None:
        timelines = build_request_timelines(
            [
                {
                    "event_id": "baseline-0-response",
                    "request_id": "baseline-0",
                    "timestamp": 18.0,
                    "mode": "db_only",
                    "event_type": "response_sent",
                    "stage": "response",
                    "duration_ms": 0,
                    "metadata": {"total_duration_ms": 18.0},
                },
                {
                    "event_id": "reference-0-hit",
                    "request_id": "reference-0",
                    "timestamp": 1.2,
                    "mode": "redis_only_reference",
                    "event_type": "cache_hit",
                    "stage": "redis_lookup",
                    "duration_ms": 1.2,
                    "metadata": {},
                },
            ]
        )

        self.assertEqual(timelines[0]["path_summary"], "App -> DB -> Response")
        self.assertEqual(timelines[1]["path_summary"], "App -> Redis -> Response")


if __name__ == "__main__":
    unittest.main()

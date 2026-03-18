from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.benchmark.models import RunConfig, RunRecord, utc_now_iso
from app.storage.run_store import RunStore


class RunStoreTest(unittest.TestCase):
    def test_run_store_writes_and_reads_run(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            store = RunStore(Path(tmp_dir))
            now = utc_now_iso()
            record = RunRecord(
                run_id="run_test",
                status="queued",
                config=RunConfig(
                    scenario="detail_page",
                    iteration_count=5,
                    concurrency=1,
                    hit_rate_buckets=[0, 50, 100],
                    ttl_seconds=30,
                ),
                created_at=now,
                updated_at=now,
            )

            store.write_run(record)
            loaded = store.read_run("run_test")

            self.assertEqual(loaded.run_id, "run_test")
            self.assertEqual(loaded.config.scenario, "detail_page")
            self.assertEqual(loaded.config.hit_rate_buckets, [0, 50, 100])

    def test_run_store_reads_empty_events_and_logs(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            store = RunStore(Path(tmp_dir))

            self.assertEqual(store.read_events("missing"), [])
            self.assertEqual(store.read_logs("missing"), [])

    def test_run_store_lists_runs_and_filters_active(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            store = RunStore(Path(tmp_dir))
            now = utc_now_iso()
            queued = RunRecord(
                run_id="run_active",
                status="queued",
                config=RunConfig("detail_page", 2, 1, [0, 100], 10),
                created_at=now,
                updated_at=now,
            )
            completed = RunRecord(
                run_id="run_done",
                status="completed",
                config=RunConfig("detail_page", 2, 1, [0, 100], 10),
                created_at=now,
                updated_at=now,
            )
            store.write_run(queued)
            store.write_run(completed)

            runs = store.list_runs()

            self.assertEqual(len(runs), 2)
            self.assertTrue(store.has_active_run())

    def test_run_store_reads_events_after_timestamp(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            store = RunStore(Path(tmp_dir))
            now = utc_now_iso()
            record = RunRecord(
                run_id="run_events",
                status="queued",
                config=RunConfig("detail_page", 2, 1, [0, 100], 10),
                created_at=now,
                updated_at=now,
            )
            store.write_run(record)
            store.append_event("run_events", _FakeEvent("evt_1", 1.0))
            store.append_event("run_events", _FakeEvent("evt_2", 2.5))

            events = store.read_events_after("run_events", 1.5)

            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["event_id"], "evt_2")

    def test_run_store_appends_log_metadata(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            store = RunStore(Path(tmp_dir))
            now = utc_now_iso()
            record = RunRecord(
                run_id="run_logs",
                status="queued",
                config=RunConfig("detail_page", 2, 1, [0, 100], 10),
                created_at=now,
                updated_at=now,
            )
            store.write_run(record)
            store.append_log("run_logs", "INFO", "warmup", "warmup completed", {"warmup_count": 2})

            logs = store.read_logs("run_logs")

            self.assertEqual(len(logs), 1)
            self.assertEqual(logs[0]["stage"], "warmup")
            self.assertEqual(logs[0]["metadata"]["warmup_count"], 2)


class _FakeEvent:
    def __init__(self, event_id: str, timestamp: float) -> None:
        self._event_id = event_id
        self._timestamp = timestamp

    def to_dict(self) -> dict:
        return {
            "event_id": self._event_id,
            "request_id": "req",
            "timestamp": self._timestamp,
            "mode": "db_only",
            "event_type": "request_started",
            "stage": "request",
            "duration_ms": 0,
            "metadata": {},
        }


if __name__ == "__main__":
    unittest.main()

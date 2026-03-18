from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from app.api.contracts import serialize_run_list_item
from app.benchmark.models import RunConfig, RunRecord, RunSummary


def build_run_id() -> str:
    return f"run_{int(time.time() * 1000)}"


class RunStore:
    def __init__(self, root: Path | None = None) -> None:
        self._root = root or Path(".tmp/runs")
        self._root.mkdir(parents=True, exist_ok=True)

    def write_run(self, record: RunRecord) -> None:
        self._run_path(record.run_id).write_text(
            json.dumps(record.to_dict(), ensure_ascii=True, indent=2),
            encoding="utf-8",
        )

    def read_run(self, run_id: str) -> RunRecord:
        payload = json.loads(self._run_path(run_id).read_text(encoding="utf-8"))
        config = RunConfig(**payload["config"])
        summary_payload = payload.get("summary")
        summary = RunSummary(**summary_payload) if summary_payload else None
        return RunRecord(
            run_id=payload["run_id"],
            status=payload["status"],
            config=config,
            created_at=payload["created_at"],
            updated_at=payload["updated_at"],
            started_at=payload.get("started_at"),
            finished_at=payload.get("finished_at"),
            summary=summary,
            error_message=payload.get("error_message"),
            mini_redis_commit=payload.get("mini_redis_commit"),
            app_commit=payload.get("app_commit"),
        )

    def append_event(self, run_id: str, event: Any) -> None:
        with self._events_path(run_id).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.to_dict(), ensure_ascii=True) + "\n")

    def read_events(self, run_id: str) -> list[dict]:
        path = self._events_path(run_id)
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]

    def read_events_after(self, run_id: str, after_timestamp: float | None) -> list[dict]:
        events = self.read_events(run_id)
        if after_timestamp is None:
            return events
        return [event for event in events if float(event.get("timestamp", 0)) > after_timestamp]

    def append_log(
        self,
        run_id: str,
        level: str,
        stage: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "timestamp": time.time(),
            "level": level,
            "stage": stage,
            "message": message,
            "metadata": metadata or {},
        }
        with self._logs_path(run_id).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=True) + "\n")

    def read_logs(self, run_id: str) -> list[dict]:
        path = self._logs_path(run_id)
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]

    def list_runs(self) -> list[dict]:
        runs: list[dict] = []
        for path in sorted(self._root.glob("run_*.json"), reverse=True):
            payload = json.loads(path.read_text(encoding="utf-8"))
            runs.append(serialize_run_list_item(payload))
        return runs

    def has_active_run(self) -> bool:
        active_statuses = {
            "queued",
            "bootstrapping",
            "warming_up",
            "running_baseline",
            "running_cache",
            "running_reference",
            "aggregating",
        }
        return any(run["status"] in active_statuses for run in self.list_runs())

    def _run_path(self, run_id: str) -> Path:
        return self._root / f"{run_id}.json"

    def _events_path(self, run_id: str) -> Path:
        return self._root / f"{run_id}.events.jsonl"

    def _logs_path(self, run_id: str) -> Path:
        return self._root / f"{run_id}.logs.jsonl"

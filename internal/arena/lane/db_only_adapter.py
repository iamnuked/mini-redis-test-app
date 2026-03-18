from __future__ import annotations

import time
from typing import Iterable

from internal.arena.gateway.models import ArenaRequest, CacheResult, LaneResult
from internal.arena.gateway.models import LaneMetrics
from internal.arena.mongo.repository import ArenaRepository


class DBOnlyLaneAdapter:
    lane_name = "db_only"

    def __init__(self, repository: ArenaRepository) -> None:
        self._repository = repository

    def _set_answer(self) -> tuple[str, str]:
        return ("OK", "ok")

    def _get_answer(self, value: str | None) -> tuple[str, str]:
        if value is None:
            return ("(nil)", "nil")
        return (value, "value")

    def _delete_answer(self, deleted: bool) -> tuple[str, str]:
        if deleted:
            return ("deleted", "deleted")
        return ("not found", "not_found")

    async def execute(self, request: ArenaRequest) -> LaneResult:
        started_at = time.perf_counter()
        started_at_ns = time.perf_counter_ns()
        path: list[str] = []
        storage_changes: list[str] = []
        value_preview: str | None = None
        answer_text: str | None = None
        answer_kind: str | None = None
        mongo_reads = 0
        db_time_ms = 0.0

        try:
            if request.command == "SET":
                db_started_at = time.perf_counter()
                write_state = self._repository.write(request.key, request.value or "")
                db_time_ms += (time.perf_counter() - db_started_at) * 1000
                path.append("mongo_write")
                storage_changes.append(f"Mongo document {write_state}")
                value_preview = request.value
                answer_text, answer_kind = self._set_answer()

            elif request.command == "GET":
                path.append("mongo_read")
                mongo_reads = 1
                db_started_at = time.perf_counter()
                value_preview = self._repository.read(request.key)
                db_time_ms += (time.perf_counter() - db_started_at) * 1000
                if value_preview is None:
                    storage_changes.append("Mongo document missing")
                else:
                    storage_changes.append("Mongo document read")
                answer_text, answer_kind = self._get_answer(value_preview)

            elif request.command == "DEL":
                path.append("mongo_delete")
                db_started_at = time.perf_counter()
                deleted = self._repository.delete(request.key)
                db_time_ms += (time.perf_counter() - db_started_at) * 1000
                storage_changes.append("Mongo document deleted" if deleted else "Mongo unchanged")
                answer_text, answer_kind = self._delete_answer(deleted)

            service_time_ms = round((time.perf_counter() - started_at) * 1000, 3)
            return LaneResult(
                request_id=request.request_id,
                lane=self.lane_name,
                status="ok",
                latency_ms=service_time_ms,
                answer_text=answer_text,
                answer_kind=answer_kind,
                value_preview=value_preview,
                path=path,
                storage_changes=storage_changes,
                cache=CacheResult(),
                mongo_reads=mongo_reads,
                metrics=LaneMetrics(
                    service_time_ms=service_time_ms,
                    db_time_ms=round(db_time_ms, 3),
                    started_at_ns=started_at_ns,
                    finished_at_ns=time.perf_counter_ns(),
                ),
            )
        except Exception as exc:
            service_time_ms = round((time.perf_counter() - started_at) * 1000, 3)
            return LaneResult(
                request_id=request.request_id,
                lane=self.lane_name,
                status="error",
                latency_ms=service_time_ms,
                answer_text=f"error: {exc}",
                answer_kind="error",
                value_preview=str(exc),
                path=path,
                storage_changes=storage_changes or ["DB only lane execution failed"],
                cache=CacheResult(),
                mongo_reads=mongo_reads,
                metrics=LaneMetrics(
                    service_time_ms=service_time_ms,
                    db_time_ms=round(db_time_ms, 3),
                    started_at_ns=started_at_ns,
                    finished_at_ns=time.perf_counter_ns(),
                ),
            )

    def clear(self, keys: Iterable[str]) -> None:
        self._repository.delete_many(keys)

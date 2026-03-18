from __future__ import annotations

import time


class BaselineClient:
    def __init__(self, db_latency_ms: float = 18.0) -> None:
        self._db_latency_ms = db_latency_ms

    @property
    def db_latency_ms(self) -> float:
        return self._db_latency_ms

    def fetch_detail(self, record_id: str) -> dict[str, str]:
        time.sleep(self._db_latency_ms / 1000.0)
        return {
            "id": record_id,
            "title": f"Detail {record_id}",
            "body": f"Body for {record_id}",
        }

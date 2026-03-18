from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Iterable, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from internal.arena.common.models import ArenaRequest
from internal.arena.common.models import LaneResult
from internal.arena.common.models import ResetStateInput
from internal.arena.common.models import SeedStateInput


class ArenaLaneExecutor(Protocol):
    async def execute(self, request: ArenaRequest) -> LaneResult:
        ...

    async def clear(self, keys: Iterable[str]) -> None:
        ...


@dataclass
class ArenaLaneClientSettings:
    name: str
    base_url: str
    timeout_seconds: float = 5.0


@dataclass
class ArenaLaneHttpClient:
    settings: ArenaLaneClientSettings

    async def execute(self, request: ArenaRequest) -> LaneResult:
        started_at = perf_counter()
        payload = await asyncio.to_thread(self._post_json, "/execute", request.to_dict())
        lane_result = LaneResult.from_dict(payload)
        lane_result.metrics.gateway_round_trip_ms = round(
            (perf_counter() - started_at) * 1000,
            3,
        )
        return lane_result

    async def clear(self, keys: Iterable[str]) -> None:
        reset_input = ResetStateInput(keys=list(keys))
        await asyncio.to_thread(self._post_json, "/reset", reset_input.to_dict())

    async def seed(self, seed_input: SeedStateInput) -> None:
        await asyncio.to_thread(self._post_json, "/seed", seed_input.to_dict())

    async def health(self) -> dict[str, Any]:
        return await asyncio.to_thread(self._get_json, "/health")

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.settings.base_url}{path}"
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        return self._open_json(request)

    def _get_json(self, path: str) -> dict[str, Any]:
        request = Request(f"{self.settings.base_url}{path}", method="GET")
        return self._open_json(request)

    def _open_json(self, request: Request) -> dict[str, Any]:
        try:
            with urlopen(request, timeout=self.settings.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"{self.settings.name} request failed with HTTP {exc.code}: {body}"
            ) from exc
        except URLError as exc:
            raise RuntimeError(f"{self.settings.name} request failed: {exc.reason}") from exc

        if not body:
            return {}
        return json.loads(body)

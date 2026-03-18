from __future__ import annotations

from internal.arena.scenario.models import ScenarioAction


def build_hot_key_plan(users: int, duration_seconds: int) -> list[ScenarioAction]:
    total_reads = max(users * duration_seconds, 1)
    key = "s:hot"
    value = '{"name":"arena-hot-key"}'

    plan = [ScenarioAction(command="SET", key=key, value=value)]
    plan.extend(
        ScenarioAction(command="GET", key=key, delay_seconds=0.05) for _ in range(total_reads)
    )
    return plan

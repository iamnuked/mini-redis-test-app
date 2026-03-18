from __future__ import annotations

from internal.arena.scenario.models import ScenarioAction


def build_ttl_expiry_plan(
    users: int,
    duration_seconds: int,
    ttl_seconds: int,
) -> list[ScenarioAction]:
    warmup_reads = max(users, 1)
    post_expiry_reads = max(duration_seconds // 2, 1)
    key = "s:ttl"
    value = '{"name":"arena-ttl"}'

    plan = [ScenarioAction(command="SET", key=key, value=value)]
    plan.extend(
        ScenarioAction(command="GET", key=key, delay_seconds=0.2) for _ in range(warmup_reads)
    )
    plan.append(ScenarioAction(command="GET", key=key, delay_seconds=ttl_seconds + 0.25))
    plan.extend(
        ScenarioAction(command="GET", key=key, delay_seconds=0.2)
        for _ in range(post_expiry_reads)
    )
    return plan

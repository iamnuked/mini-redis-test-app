from __future__ import annotations

from internal.arena.scenario.models import ScenarioAction
from internal.arena.scenario.models import ScenarioPlan


READ_LEVELS = {0, 20, 40, 60, 80, 100}
CATALOG_SIZE = 24
HOTSET_SIZE = 4
ACTION_DELAY_SECONDS = 0.05


def build_read_plan(
    users: int,
    duration_seconds: int,
    hot_percent: int,
) -> ScenarioPlan:
    if hot_percent not in READ_LEVELS:
        raise ValueError(f"Unsupported read hot percent: {hot_percent}")

    documents = _build_catalog_documents()
    total_reads = max(users * duration_seconds, 1)
    keys = list(documents.keys())
    hot_keys = keys[:HOTSET_SIZE]
    cold_keys = keys[HOTSET_SIZE:]

    actions: list[ScenarioAction] = []
    for index in range(total_reads):
        is_hot = ((index * 37) % 100) < hot_percent
        pool = hot_keys if is_hot else cold_keys
        key = pool[index % len(pool)]
        actions.append(
            ScenarioAction(
                command="GET",
                key=key,
                delay_seconds=ACTION_DELAY_SECONDS,
            )
        )

    return ScenarioPlan(actions=actions, seed_documents=documents)


def build_write_plan(users: int, duration_seconds: int) -> ScenarioPlan:
    total_writes = max(users * duration_seconds, 1)
    actions: list[ScenarioAction] = []
    for index in range(total_writes):
        key = f"s:w:{index:03d}"
        value = _value_for_index(index, tag="write")
        actions.append(
            ScenarioAction(
                command="SET",
                key=key,
                value=value,
                delay_seconds=ACTION_DELAY_SECONDS,
            )
        )
    return ScenarioPlan(actions=actions, seed_documents={})


def build_mixed_plan(users: int, duration_seconds: int) -> ScenarioPlan:
    documents = _build_catalog_documents()
    total_ops = max(users * duration_seconds, 1)
    keys = list(documents.keys())
    hot_keys = keys[:HOTSET_SIZE]
    cold_keys = keys[HOTSET_SIZE:]

    actions: list[ScenarioAction] = []
    for index in range(total_ops):
        phase = index % 10
        if phase <= 5:
            use_hot = phase in {0, 1, 2, 3}
            pool = hot_keys if use_hot else cold_keys
            key = pool[index % len(pool)]
            actions.append(
                ScenarioAction(
                    command="GET",
                    key=key,
                    delay_seconds=ACTION_DELAY_SECONDS,
                )
            )
            continue

        if phase in {6, 7}:
            key = hot_keys[index % len(hot_keys)] if phase == 6 else f"s:m:w:{index:03d}"
            actions.append(
                ScenarioAction(
                    command="SET",
                    key=key,
                    value=_value_for_index(index, tag="mixed"),
                    delay_seconds=ACTION_DELAY_SECONDS,
                )
            )
            continue

        key = cold_keys[index % len(cold_keys)] if phase == 8 else hot_keys[index % len(hot_keys)]
        actions.append(
            ScenarioAction(
                command="DEL",
                key=key,
                delay_seconds=ACTION_DELAY_SECONDS,
            )
        )

    return ScenarioPlan(actions=actions, seed_documents=documents)


def _build_catalog_documents() -> dict[str, str]:
    return {
        f"s:r:{index:03d}": _value_for_index(index, tag="read")
        for index in range(CATALOG_SIZE)
    }


def _value_for_index(index: int, *, tag: str) -> str:
    return (
        "{"
        f"\"tag\":\"{tag}\","
        f"\"id\":{index},"
        f"\"title\":\"arena-{tag}-{index:03d}\","
        f"\"body\":\"payload-{(index % 7) + 1:02d}-abcdefghij\""
        "}"
    )

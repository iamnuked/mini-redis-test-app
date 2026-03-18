from __future__ import annotations

from dataclasses import dataclass

from internal.arena.gateway.models import CommandName, ScenarioId


@dataclass
class ScenarioAction:
    command: CommandName
    key: str
    value: str | None = None
    delay_seconds: float = 0.0


@dataclass
class ScenarioDescriptor:
    scenario_id: ScenarioId
    title: str
    description: str

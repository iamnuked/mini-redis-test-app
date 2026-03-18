from dataclasses import dataclass


@dataclass(frozen=True)
class Command:
    name: str
    arguments: tuple[str, ...]

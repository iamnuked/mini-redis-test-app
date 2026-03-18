from dataclasses import dataclass, field


@dataclass
class SessionContext:
    protocol_version: int = 2
    selected_db: int = 0
    client_name: str | None = None
    client_info: dict[str, str] = field(default_factory=dict)

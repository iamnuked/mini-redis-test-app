from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class MemoryProfile:
    key: str
    label: str
    max_memory_bytes: int

    def to_dict(self) -> dict[str, str | int]:
        return asdict(self)


@dataclass(frozen=True)
class TtlProfile:
    key: str
    label: str
    ttl_seconds: float

    def to_dict(self) -> dict[str, str | float]:
        return asdict(self)


MEMORY_PROFILES: dict[str, MemoryProfile] = {
    "small": MemoryProfile(key="small", label="256B", max_memory_bytes=256),
    "medium": MemoryProfile(key="medium", label="512B", max_memory_bytes=512),
    "large": MemoryProfile(key="large", label="1024B", max_memory_bytes=1024),
    "xlarge": MemoryProfile(key="xlarge", label="2048B", max_memory_bytes=2048),
}

TTL_PROFILES: dict[str, TtlProfile] = {
    "shortest": TtlProfile(key="shortest", label="0.5s", ttl_seconds=0.5),
    "short": TtlProfile(key="short", label="1s", ttl_seconds=1.0),
    "medium": TtlProfile(key="medium", label="2s", ttl_seconds=2.0),
    "steady": TtlProfile(key="steady", label="3s", ttl_seconds=3.0),
    "long": TtlProfile(key="long", label="5s", ttl_seconds=5.0),
    "xlong": TtlProfile(key="xlong", label="10s", ttl_seconds=10.0),
}

DEFAULT_MEMORY_PROFILE = "medium"
DEFAULT_TTL_PROFILE = "medium"

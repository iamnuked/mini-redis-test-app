from internal.repository.ttl_repository import TtlRepository


class InMemoryTtlRepository(TtlRepository):
    def __init__(self) -> None:
        self._ttl: dict[str, float] = {}

    def list_keys(self) -> list[str]:
        return list(self._ttl.keys())

    def get_expiration(self, key: str) -> float | None:
        return self._ttl.get(key)

    def set_expiration(self, key: str, expires_at: float) -> None:
        self._ttl[key] = expires_at

    def delete_expiration(self, key: str) -> None:
        self._ttl.pop(key, None)

from internal.repository.store_repository import StoreRepository


class InMemoryStoreRepository(StoreRepository):
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def list_keys(self) -> list[str]:
        return list(self._store.keys())

    def get(self, key: str) -> str | None:
        return self._store.get(key)

    def set(self, key: str, value: str) -> None:
        self._store[key] = value

    def delete(self, key: str) -> bool:
        return self._store.pop(key, None) is not None

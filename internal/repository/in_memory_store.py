from internal.repository.store_repository import StoreRepository
from internal.repository.value_entry import ValueEntry


class InMemoryStoreRepository(StoreRepository):
    def __init__(self) -> None:
        self._store: dict[str, ValueEntry] = {}

    def list_keys(self) -> list[str]:
        return list(self._store.keys())

    def get(self, key: str) -> ValueEntry | None:
        return self._store.get(key)

    def set(self, key: str, value: ValueEntry) -> None:
        self._store[key] = value

    def delete(self, key: str) -> bool:
        return self._store.pop(key, None) is not None

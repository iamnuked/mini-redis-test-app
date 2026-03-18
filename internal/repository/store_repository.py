from abc import ABC, abstractmethod

from internal.repository.value_entry import ValueEntry


class StoreRepository(ABC):
    @abstractmethod
    def list_keys(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def get(self, key: str) -> ValueEntry | None:
        raise NotImplementedError

    @abstractmethod
    def set(self, key: str, value: ValueEntry) -> None:
        raise NotImplementedError

    @abstractmethod
    def delete(self, key: str) -> bool:
        raise NotImplementedError

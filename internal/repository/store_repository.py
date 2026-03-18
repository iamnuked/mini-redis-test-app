from abc import ABC, abstractmethod


class StoreRepository(ABC):
    @abstractmethod
    def list_keys(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def get(self, key: str) -> str | None:
        raise NotImplementedError

    @abstractmethod
    def set(self, key: str, value: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def delete(self, key: str) -> bool:
        raise NotImplementedError

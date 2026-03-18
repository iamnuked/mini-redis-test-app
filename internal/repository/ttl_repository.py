from abc import ABC, abstractmethod


class TtlRepository(ABC):
    @abstractmethod
    def list_keys(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def get_expiration(self, key: str) -> float | None:
        raise NotImplementedError

    @abstractmethod
    def set_expiration(self, key: str, expires_at: float) -> None:
        raise NotImplementedError

    @abstractmethod
    def delete_expiration(self, key: str) -> None:
        raise NotImplementedError

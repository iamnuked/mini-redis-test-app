from internal.expiration.expiration_manager import ExpirationManager
from internal.repository.store_repository import StoreRepository


class GetService:
    def __init__(
        self,
        store_repository: StoreRepository,
        expiration_manager: ExpirationManager,
    ) -> None:
        self._store_repository = store_repository
        self._expiration_manager = expiration_manager

    def execute(self, key: str) -> str | None:
        self._expiration_manager.purge_if_expired(key)
        return self._store_repository.get(key)

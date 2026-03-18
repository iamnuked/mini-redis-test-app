from internal.expiration.expiration_manager import ExpirationManager
from internal.repository.store_repository import StoreRepository
from internal.repository.ttl_repository import TtlRepository


class DelService:
    def __init__(
        self,
        store_repository: StoreRepository,
        ttl_repository: TtlRepository,
        expiration_manager: ExpirationManager,
    ) -> None:
        self._store_repository = store_repository
        self._ttl_repository = ttl_repository
        self._expiration_manager = expiration_manager

    def execute(self, key: str) -> int:
        if self._expiration_manager.purge_if_expired(key):
            return 0

        deleted = self._store_repository.delete(key)
        if not deleted:
            return 0

        self._ttl_repository.delete_expiration(key)
        return 1

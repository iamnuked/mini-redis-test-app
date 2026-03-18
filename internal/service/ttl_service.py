from internal.expiration.expiration_manager import ExpirationManager
from internal.repository.store_repository import StoreRepository
from internal.repository.ttl_repository import TtlRepository


class TtlService:
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
            return -2

        if self._store_repository.get(key) is None:
            return -2

        if self._ttl_repository.get_expiration(key) is None:
            return -1

        remaining_seconds = self._expiration_manager.calculate_remaining_seconds(key)
        if remaining_seconds is None:
            return -1
        return remaining_seconds

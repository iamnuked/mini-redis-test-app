from internal.clock.clock import Clock
from internal.repository.store_repository import StoreRepository
from internal.repository.ttl_repository import TtlRepository


class ExpirationManager:
    def __init__(
        self,
        clock: Clock,
        store_repository: StoreRepository,
        ttl_repository: TtlRepository,
    ) -> None:
        self._clock = clock
        self._store_repository = store_repository
        self._ttl_repository = ttl_repository

    def purge_if_expired(self, key: str) -> bool:
        expires_at = self._ttl_repository.get_expiration(key)
        if expires_at is None:
            return False
        if self._clock.now() < expires_at:
            return False
        self._store_repository.delete(key)
        self._ttl_repository.delete_expiration(key)
        return True

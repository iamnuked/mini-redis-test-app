from internal.clock.clock import Clock
from internal.expiration.ttl_calculator import TtlCalculator
from internal.repository.store_repository import StoreRepository
from internal.repository.ttl_repository import TtlRepository


class ExpirationManager:
    def __init__(
        self,
        clock: Clock,
        ttl_calculator: TtlCalculator,
        store_repository: StoreRepository,
        ttl_repository: TtlRepository,
    ) -> None:
        self._clock = clock
        self._ttl_calculator = ttl_calculator
        self._store_repository = store_repository
        self._ttl_repository = ttl_repository

    def is_expired(self, key: str) -> bool:
        expires_at = self._ttl_repository.get_expiration(key)
        if expires_at is None:
            return False
        return self._ttl_calculator.is_expired(self._clock.now(), expires_at)

    def purge_if_expired(self, key: str) -> bool:
        if not self.is_expired(key):
            return False
        self._delete_key(key)
        return True

    def calculate_remaining_seconds(self, key: str) -> int | None:
        expires_at = self._ttl_repository.get_expiration(key)
        if expires_at is None:
            return None
        return self._ttl_calculator.calculate_remaining_seconds(
            self._clock.now(),
            expires_at,
        )

    def _delete_key(self, key: str) -> None:
        self._store_repository.delete(key)
        self._ttl_repository.delete_expiration(key)

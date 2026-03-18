from internal.clock.clock import Clock
from internal.expiration.expiration_manager import ExpirationManager
from internal.expiration.ttl_calculator import TtlCalculator
from internal.repository.store_repository import StoreRepository
from internal.repository.ttl_repository import TtlRepository


class ExpireService:
    def __init__(
        self,
        clock: Clock,
        ttl_calculator: TtlCalculator,
        store_repository: StoreRepository,
        ttl_repository: TtlRepository,
        expiration_manager: ExpirationManager,
    ) -> None:
        self._clock = clock
        self._ttl_calculator = ttl_calculator
        self._store_repository = store_repository
        self._ttl_repository = ttl_repository
        self._expiration_manager = expiration_manager

    def execute(self, key: str, ttl_seconds: int) -> int:
        if self._expiration_manager.purge_if_expired(key):
            return 0

        if self._store_repository.get(key) is None:
            return 0

        expires_at = self._ttl_calculator.calculate_expires_at(
            self._clock.now(),
            ttl_seconds,
        )
        self._ttl_repository.set_expiration(key, expires_at)
        return 1

from internal.clock.clock import Clock
from internal.repository.store_repository import StoreRepository
from internal.repository.ttl_repository import TtlRepository


class ExpirationSweeper:
    def __init__(
        self,
        clock: Clock,
        store_repository: StoreRepository,
        ttl_repository: TtlRepository,
        sweep_batch_size: int = 100,
    ) -> None:
        self._clock = clock
        self._store_repository = store_repository
        self._ttl_repository = ttl_repository
        self._sweep_batch_size = sweep_batch_size
        self._running = False

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False

    def is_running(self) -> bool:
        return self._running

    def sweep_once(self) -> int:
        removed_count = 0
        now = self._clock.now()
        keys = self._ttl_repository.list_keys()

        for key in keys[: self._sweep_batch_size]:
            expires_at = self._ttl_repository.get_expiration(key)
            if expires_at is None:
                continue
            if not self._is_expired(now, expires_at):
                continue
            self._store_repository.delete(key)
            self._ttl_repository.delete_expiration(key)
            removed_count += 1

        return removed_count

    def _is_expired(self, now: float, expires_at: float) -> bool:
        return now >= expires_at

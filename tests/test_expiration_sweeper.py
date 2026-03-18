from internal.clock.fake_clock import FakeClock
from internal.expiration.expiration_sweeper import ExpirationSweeper
from internal.repository.in_memory_store import InMemoryStoreRepository
from internal.repository.in_memory_ttl import InMemoryTtlRepository


def test_sweep_once_removes_expired_keys() -> None:
    clock = FakeClock(current_time=10.0)
    store = InMemoryStoreRepository()
    ttl = InMemoryTtlRepository()
    sweeper = ExpirationSweeper(
        clock=clock,
        store_repository=store,
        ttl_repository=ttl,
        sweep_interval_seconds=1,
        sweep_batch_size=10,
    )
    store.set("expired", "value")
    ttl.set_expiration("expired", 5.0)

    removed_count = sweeper.sweep_once()

    assert removed_count == 1
    assert store.get("expired") is None
    assert ttl.get_expiration("expired") is None


def test_start_and_stop_update_running_state() -> None:
    sweeper = ExpirationSweeper(
        clock=FakeClock(current_time=0.0),
        store_repository=InMemoryStoreRepository(),
        ttl_repository=InMemoryTtlRepository(),
        sweep_interval_seconds=1,
        sweep_batch_size=10,
    )

    sweeper.start()
    assert sweeper.is_running() is True

    sweeper.stop()
    assert sweeper.is_running() is False

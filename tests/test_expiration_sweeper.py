import time

from internal.clock.fake_clock import FakeClock
from internal.expiration.expiration_sweeper import ExpirationSweeper
from internal.repository.in_memory_store import InMemoryStoreRepository
from internal.repository.in_memory_ttl import InMemoryTtlRepository
from internal.repository.value_entry import ValueEntry, ValueType


def test_sweep_once_removes_expired_keys() -> None:
    clock = FakeClock(current_time=100.0)
    store_repository = InMemoryStoreRepository()
    ttl_repository = InMemoryTtlRepository()
    store_repository.set(
        "expired",
        ValueEntry(value_type=ValueType.STRING, value="value"),
    )
    ttl_repository.set_expiration("expired", 99.0)

    sweeper = ExpirationSweeper(
        clock=clock,
        store_repository=store_repository,
        ttl_repository=ttl_repository,
        sweep_batch_size=10,
    )

    removed_count = sweeper.sweep_once()

    assert removed_count == 1
    assert store_repository.get("expired") is None
    assert ttl_repository.get_expiration("expired") is None


def test_start_and_stop_update_running_state() -> None:
    sweeper = ExpirationSweeper(
        clock=FakeClock(current_time=100.0),
        store_repository=InMemoryStoreRepository(),
        ttl_repository=InMemoryTtlRepository(),
    )

    sweeper.start()
    assert sweeper.is_running() is True

    sweeper.stop()
    assert sweeper.is_running() is False


def test_start_is_idempotent_when_already_running() -> None:
    sweeper = ExpirationSweeper(
        clock=FakeClock(current_time=100.0),
        store_repository=InMemoryStoreRepository(),
        ttl_repository=InMemoryTtlRepository(),
        sweep_interval_seconds=1,
    )

    sweeper.start()
    first_worker = sweeper._worker
    sweeper.start()

    assert sweeper._worker is first_worker
    sweeper.stop()


def test_background_worker_runs_sweep_loop() -> None:
    sweeper = ExpirationSweeper(
        clock=FakeClock(current_time=100.0),
        store_repository=InMemoryStoreRepository(),
        ttl_repository=InMemoryTtlRepository(),
        sweep_interval_seconds=1,
    )
    sweep_calls: list[str] = []

    def fake_sweep_once() -> int:
        sweep_calls.append("called")
        sweeper.stop()
        return 0

    sweeper.sweep_once = fake_sweep_once  # type: ignore[method-assign]

    sweeper.start()
    time.sleep(1.2)

    assert sweep_calls == ["called"]
    assert sweeper.is_running() is False


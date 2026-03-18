from internal.server.shutdown import ShutdownManager


def test_shutdown_manager_starts_without_shutdown_request() -> None:
    manager = ShutdownManager()

    assert manager.is_shutdown_requested() is False


def test_shutdown_manager_marks_shutdown_requested() -> None:
    manager = ShutdownManager()

    manager.request_shutdown()

    assert manager.is_shutdown_requested() is True

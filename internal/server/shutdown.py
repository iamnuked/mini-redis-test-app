class ShutdownManager:
    def __init__(self) -> None:
        self._shutdown_requested = False

    def request_shutdown(self) -> None:
        self._shutdown_requested = True

    def is_shutdown_requested(self) -> bool:
        return self._shutdown_requested

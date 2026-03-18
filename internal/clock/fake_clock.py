from internal.clock.clock import Clock


class FakeClock(Clock):
    def __init__(self, current_time: float = 0.0) -> None:
        self._current_time = current_time

    def now(self) -> float:
        return self._current_time

    def advance(self, seconds: float) -> None:
        self._current_time += seconds

import time

from internal.clock.clock import Clock


class SystemClock(Clock):
    def now(self) -> float:
        return time.time()

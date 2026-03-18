import time
import unittest

from internal.clock.fake_clock import FakeClock
from internal.clock.system_clock import SystemClock


class FakeClockTest(unittest.TestCase):
    def test_fake_clock_returns_initial_time(self) -> None:
        clock = FakeClock(current_time=12.5)
        self.assertEqual(clock.now(), 12.5)

    def test_fake_clock_advance_updates_current_time(self) -> None:
        clock = FakeClock(current_time=1.0)
        clock.advance(2.5)
        self.assertEqual(clock.now(), 3.5)


class SystemClockTest(unittest.TestCase):
    def test_system_clock_returns_current_timestamp(self) -> None:
        before = time.time()
        current = SystemClock().now()
        after = time.time()

        self.assertIsInstance(current, float)
        self.assertGreaterEqual(current, before)
        self.assertLessEqual(current, after)

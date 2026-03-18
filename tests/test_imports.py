import unittest

from internal.clock.fake_clock import FakeClock
from internal.config.runtime_config import RuntimeConfig
from tests.support import load_cli_main_module


class ImportSmokeTest(unittest.TestCase):
    def test_assignee_four_modules_can_be_loaded(self) -> None:
        config = RuntimeConfig.default()
        clock = FakeClock()
        cli_module = load_cli_main_module()

        self.assertIsNotNone(config)
        self.assertEqual(clock.now(), 0.0)
        self.assertTrue(hasattr(cli_module, "main"))

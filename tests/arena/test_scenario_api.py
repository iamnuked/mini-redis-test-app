import unittest

from pydantic import ValidationError

from internal.arena.api.scenario_api import ScenarioRunPayload


class ScenarioApiPayloadTests(unittest.TestCase):
    def test_accepts_current_read_hot_levels(self) -> None:
        for level in [0, 20, 40, 60, 80, 100]:
            payload = ScenarioRunPayload(
                scenario_id="read",
                users=2,
                duration_seconds=3,
                read_hot_percent=level,
                ttl_enabled=True,
                ttl_seconds=2.0,
            )
            self.assertEqual(payload.read_hot_percent, level)

    def test_rejects_legacy_read_hot_levels(self) -> None:
        with self.assertRaises(ValidationError):
            ScenarioRunPayload(
                scenario_id="read",
                users=2,
                duration_seconds=3,
                read_hot_percent=25,
                ttl_enabled=True,
                ttl_seconds=2.0,
            )


if __name__ == "__main__":
    unittest.main()

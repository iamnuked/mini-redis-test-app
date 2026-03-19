import unittest

from internal.arena.scenario.workloads import build_mixed_plan
from internal.arena.scenario.workloads import build_read_plan
from internal.arena.scenario.workloads import build_write_plan


class ScenarioWorkloadTests(unittest.TestCase):
    def test_read_plan_seeds_catalog_and_generates_only_get_actions(self) -> None:
        plan = build_read_plan(users=2, duration_seconds=3, hot_percent=80)

        self.assertEqual(len(plan.seed_documents), 24)
        self.assertEqual(len(plan.actions), 6)
        self.assertTrue(all(action.command == "GET" for action in plan.actions))
        self.assertTrue(all(action.key.startswith("s:r:") for action in plan.actions))

    def test_write_plan_generates_only_set_actions_without_seed(self) -> None:
        plan = build_write_plan(users=2, duration_seconds=2)

        self.assertEqual(plan.seed_documents, {})
        self.assertEqual(len(plan.actions), 4)
        self.assertTrue(all(action.command == "SET" for action in plan.actions))
        self.assertTrue(all(action.key.startswith("s:w:") for action in plan.actions))

    def test_mixed_plan_seeds_catalog_and_contains_get_set_del(self) -> None:
        plan = build_mixed_plan(users=2, duration_seconds=5)

        self.assertEqual(len(plan.seed_documents), 24)
        self.assertEqual(len(plan.actions), 10)
        commands = {action.command for action in plan.actions}
        self.assertEqual(commands, {"GET", "SET", "DEL"})


if __name__ == "__main__":
    unittest.main()

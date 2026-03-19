import unittest

from pydantic import ValidationError

from internal.arena.api.manual_command_api import ManualCommandPayload


class ManualCommandPayloadTests(unittest.TestCase):
    def test_set_requires_value(self) -> None:
        with self.assertRaises(ValidationError):
            ManualCommandPayload(command="SET", key="user:1")

    def test_hset_requires_field_and_value(self) -> None:
        with self.assertRaises(ValidationError):
            ManualCommandPayload(command="HSET", key="user:1", value="kim")

        with self.assertRaises(ValidationError):
            ManualCommandPayload(command="HSET", key="user:1", field="name")

    def test_hget_requires_field(self) -> None:
        with self.assertRaises(ValidationError):
            ManualCommandPayload(command="HGET", key="user:1")

    def test_get_and_del_clear_value_and_field(self) -> None:
        get_payload = ManualCommandPayload(
            command="GET",
            key="user:1",
            field="name",
            value="ignored",
        )
        del_payload = ManualCommandPayload(
            command="DEL",
            key="user:1",
            field="name",
            value="ignored",
        )

        self.assertIsNone(get_payload.field)
        self.assertIsNone(get_payload.value)
        self.assertIsNone(del_payload.field)
        self.assertIsNone(del_payload.value)

    def test_hgetall_clears_field_and_value(self) -> None:
        payload = ManualCommandPayload(
            command="HGETALL",
            key="user:1",
            field="name",
            value="ignored",
        )

        self.assertIsNone(payload.field)
        self.assertIsNone(payload.value)


if __name__ == "__main__":
    unittest.main()

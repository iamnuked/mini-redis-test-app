from __future__ import annotations

import unittest
from unittest.mock import patch

from app.adapters.mini_redis import MiniRedisClient


class _FakeSocket:
    def __init__(self, responses: list[bytes]) -> None:
        self._responses = bytearray(b"".join(responses))
        self.sent_packets: list[bytes] = []
        self.timeout = None
        self.closed = False

    def settimeout(self, value: float) -> None:
        self.timeout = value

    def sendall(self, payload: bytes) -> None:
        self.sent_packets.append(payload)

    def recv(self, size: int) -> bytes:
        if not self._responses:
            return b""
        chunk = bytes(self._responses[:size])
        del self._responses[:size]
        return chunk

    def close(self) -> None:
        self.closed = True


class MiniRedisClientUnitTest(unittest.TestCase):
    def test_client_reuses_single_connection_for_multiple_commands(self) -> None:
        fake_socket = _FakeSocket(
            [
                b"+OK\r\n",
                b"$5\r\nvalue\r\n",
            ]
        )

        with patch("app.adapters.mini_redis.socket.create_connection", return_value=fake_socket) as create_connection:
            client = MiniRedisClient(host="127.0.0.1", port=6379, timeout_seconds=1.0)
            self.assertTrue(client.set("benchmark:key", "value"))
            self.assertEqual(client.get("benchmark:key"), "value")
            client.close()

        self.assertEqual(create_connection.call_count, 1)
        self.assertEqual(len(fake_socket.sent_packets), 2)
        self.assertTrue(fake_socket.closed)

    def test_client_retries_once_when_previous_connection_returns_empty_response(self) -> None:
        stale_socket = _FakeSocket([])
        healthy_socket = _FakeSocket([b"+OK\r\n"])

        with patch(
            "app.adapters.mini_redis.socket.create_connection",
            side_effect=[stale_socket, healthy_socket],
        ) as create_connection:
            client = MiniRedisClient(host="127.0.0.1", port=6379, timeout_seconds=1.0)
            self.assertTrue(client.set("benchmark:key", "value"))
            client.close()

        self.assertEqual(create_connection.call_count, 2)
        self.assertEqual(len(stale_socket.sent_packets), 1)
        self.assertEqual(len(healthy_socket.sent_packets), 1)
        self.assertTrue(stale_socket.closed)
        self.assertTrue(healthy_socket.closed)


if __name__ == "__main__":
    unittest.main()

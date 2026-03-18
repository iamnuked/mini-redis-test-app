import io
import unittest
from unittest import mock

from internal.config import defaults
from tests.support import load_cli_main_module

HELLO_RESPONSE = (
    b"%3\r\n"
    b"+server\r\n"
    b"+mini-redis\r\n"
    b"+version\r\n"
    b"+1.0\r\n"
    b"+proto\r\n"
    b":3\r\n"
)


class FakeSocket:
    def __init__(self, responses: bytes) -> None:
        self._stream = io.BytesIO(responses)
        self.sent = bytearray()
        self.timeout = None

    def settimeout(self, timeout: float) -> None:
        self.timeout = timeout

    def makefile(self, mode: str):
        return self._stream

    def sendall(self, data: bytes) -> None:
        self.sent.extend(data)

    def close(self) -> None:
        self._stream.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()


class FakeConnectionFactory:
    def __init__(self, sockets):
        self._sockets = list(sockets)
        self.calls = []

    def __call__(self, address, timeout):
        self.calls.append((address, timeout))
        if not self._sockets:
            raise AssertionError("unexpected extra connection attempt")
        return self._sockets.pop(0)


class CliMainTest(unittest.TestCase):
    def setUp(self) -> None:
        self.cli_main = load_cli_main_module()

    def test_parse_cli_arguments_uses_documented_defaults(self) -> None:
        arguments = self.cli_main.parse_cli_arguments(["GET", "mykey"])

        self.assertEqual(arguments.host, defaults.DEFAULT_HOST)
        self.assertEqual(arguments.port, defaults.DEFAULT_PORT)
        self.assertEqual(arguments.command, "GET")
        self.assertEqual(arguments.command_arguments, ["mykey"])

    def test_main_returns_usage_error_when_command_is_missing(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()

        exit_code = self.cli_main.main([], stdout=stdout, stderr=stderr)

        self.assertEqual(exit_code, defaults.CLI_EXIT_USAGE_ERROR)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("usage:", stderr.getvalue())

    def test_main_returns_connection_error_when_connect_fails(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()

        with mock.patch.object(
            self.cli_main.socket,
            "create_connection",
            side_effect=OSError("refused"),
        ):
            exit_code = self.cli_main.main(["GET", "mykey"], stdout=stdout, stderr=stderr)

        self.assertEqual(exit_code, defaults.CLI_EXIT_CONNECTION_ERROR)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("connection error: refused", stderr.getvalue())

    def test_main_sends_hello_then_command_and_renders_success(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        hello_socket = FakeSocket(HELLO_RESPONSE)
        command_socket = FakeSocket(b"$5\r\nvalue\r\n")
        connection_factory = FakeConnectionFactory([hello_socket, command_socket])

        with mock.patch.object(
            self.cli_main.socket,
            "create_connection",
            side_effect=connection_factory,
        ):
            exit_code = self.cli_main.main(
                [
                    "--host",
                    defaults.DEFAULT_HOST,
                    "--port",
                    str(defaults.DEFAULT_PORT),
                    "GET",
                    "mykey",
                ],
                stdout=stdout,
                stderr=stderr,
            )

        self.assertEqual(exit_code, defaults.CLI_EXIT_SUCCESS)
        self.assertEqual(stdout.getvalue(), "value\n")
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(
            bytes(hello_socket.sent),
            self.cli_main.build_hello_frame(),
        )
        self.assertEqual(
            bytes(command_socket.sent),
            self.cli_main.build_command_frame("GET", ["mykey"]),
        )
        self.assertEqual(
            connection_factory.calls,
            [
                (
                    (defaults.DEFAULT_HOST, defaults.DEFAULT_PORT),
                    defaults.DEFAULT_CONNECT_TIMEOUT_SECONDS,
                ),
                (
                    (defaults.DEFAULT_HOST, defaults.DEFAULT_PORT),
                    defaults.DEFAULT_CONNECT_TIMEOUT_SECONDS,
                ),
            ],
        )
        self.assertEqual(
            hello_socket.timeout,
            max(
                defaults.DEFAULT_READ_TIMEOUT_SECONDS,
                defaults.DEFAULT_WRITE_TIMEOUT_SECONDS,
            ),
        )
        self.assertEqual(
            command_socket.timeout,
            max(
                defaults.DEFAULT_READ_TIMEOUT_SECONDS,
                defaults.DEFAULT_WRITE_TIMEOUT_SECONDS,
            ),
        )

    def test_main_returns_server_error_when_server_responds_with_error(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        hello_socket = FakeSocket(HELLO_RESPONSE)
        command_socket = FakeSocket(b"-ERR unsupported command\r\n")
        connection_factory = FakeConnectionFactory([hello_socket, command_socket])

        with mock.patch.object(
            self.cli_main.socket,
            "create_connection",
            side_effect=connection_factory,
        ):
            exit_code = self.cli_main.main(
                [
                    "--host",
                    defaults.DEFAULT_HOST,
                    "--port",
                    str(defaults.DEFAULT_PORT),
                    "NOPE",
                ],
                stdout=stdout,
                stderr=stderr,
            )

        self.assertEqual(exit_code, defaults.CLI_EXIT_SERVER_ERROR)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "ERR unsupported command\n")
        self.assertEqual(
            bytes(hello_socket.sent),
            self.cli_main.build_hello_frame(),
        )
        self.assertEqual(
            bytes(command_socket.sent),
            self.cli_main.build_command_frame("NOPE", []),
        )

    def test_main_stops_after_hello_error_without_sending_command(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        hello_socket = FakeSocket(b"-ERR unsupported protocol version\r\n")
        connection_factory = FakeConnectionFactory([hello_socket])

        with mock.patch.object(
            self.cli_main.socket,
            "create_connection",
            side_effect=connection_factory,
        ):
            exit_code = self.cli_main.main(
                [
                    "--host",
                    defaults.DEFAULT_HOST,
                    "--port",
                    str(defaults.DEFAULT_PORT),
                    "GET",
                    "mykey",
                ],
                stdout=stdout,
                stderr=stderr,
            )

        self.assertEqual(exit_code, defaults.CLI_EXIT_SERVER_ERROR)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "ERR unsupported protocol version\n")
        self.assertEqual(
            bytes(hello_socket.sent),
            self.cli_main.build_hello_frame(),
        )
        self.assertEqual(len(connection_factory.calls), 1)

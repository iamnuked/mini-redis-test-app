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
        fake_socket = FakeSocket(HELLO_RESPONSE + b"$5\r\nvalue\r\n")

        with mock.patch.object(
            self.cli_main.socket,
            "create_connection",
            return_value=fake_socket,
        ) as create_connection:
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
            bytes(fake_socket.sent),
            self.cli_main.build_hello_frame()
            + self.cli_main.build_command_frame("GET", ["mykey"]),
        )
        create_connection.assert_called_once_with(
            (defaults.DEFAULT_HOST, defaults.DEFAULT_PORT),
            timeout=defaults.DEFAULT_CONNECT_TIMEOUT_SECONDS,
        )
        self.assertEqual(
            fake_socket.timeout,
            max(
                defaults.DEFAULT_READ_TIMEOUT_SECONDS,
                defaults.DEFAULT_WRITE_TIMEOUT_SECONDS,
            ),
        )

    def test_main_returns_server_error_when_server_responds_with_error(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        fake_socket = FakeSocket(HELLO_RESPONSE + b"-ERR unsupported command\r\n")

        with mock.patch.object(
            self.cli_main.socket,
            "create_connection",
            return_value=fake_socket,
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
            bytes(fake_socket.sent),
            self.cli_main.build_hello_frame()
            + self.cli_main.build_command_frame("NOPE", []),
        )

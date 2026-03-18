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
        stdin = io.StringIO("quit\n")
        stdout = io.StringIO()
        stderr = io.StringIO()

        exit_code = self.cli_main.main([], stdin=stdin, stdout=stdout, stderr=stderr)

        self.assertEqual(exit_code, defaults.CLI_EXIT_SUCCESS)
        self.assertEqual(stdout.getvalue(), "mini-redis> ")
        self.assertEqual(stderr.getvalue(), "")

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

    def test_read_response_parses_map_payload(self) -> None:
        stream = io.BytesIO(HELLO_RESPONSE)

        response = self.cli_main.read_response(stream)

        self.assertEqual(response.kind, "map")
        self.assertEqual(
            response.value,
            {"server": "mini-redis", "version": "1.0", "proto": 3},
        )

    def test_render_response_formats_map_payload(self) -> None:
        response = self.cli_main.RespObject(
            kind="map",
            value={"server": "mini-redis", "proto": 3, "value": None},
        )

        rendered = self.cli_main.render_response(response)

        self.assertEqual(
            rendered,
            "server: mini-redis\nproto: 3\nvalue: (nil)",
        )

    def test_render_response_rejects_non_dict_map_value(self) -> None:
        response = self.cli_main.RespObject(kind="map", value="invalid")

        with self.assertRaisesRegex(ValueError, "dictionary"):
            self.cli_main.render_response(response)

    def test_repl_executes_multiple_commands_until_quit(self) -> None:
        stdin = io.StringIO("GET mykey\nSET mykey hello\nquit\n")
        stdout = io.StringIO()
        stderr = io.StringIO()
        sockets = [
            FakeSocket(HELLO_RESPONSE),
            FakeSocket(b"$5\r\nvalue\r\n"),
            FakeSocket(HELLO_RESPONSE),
            FakeSocket(b"+OK\r\n"),
        ]
        connection_factory = FakeConnectionFactory(sockets)

        with mock.patch.object(
            self.cli_main.socket,
            "create_connection",
            side_effect=connection_factory,
        ):
            exit_code = self.cli_main.main([], stdin=stdin, stdout=stdout, stderr=stderr)

        self.assertEqual(exit_code, defaults.CLI_EXIT_SUCCESS)
        self.assertEqual(
            stdout.getvalue(),
            "mini-redis> value\nmini-redis> OK\nmini-redis> ",
        )
        self.assertEqual(stderr.getvalue(), "")

    def test_repl_skips_empty_lines_and_continues_after_server_error(self) -> None:
        stdin = io.StringIO("\nNOPE\nquit\n")
        stdout = io.StringIO()
        stderr = io.StringIO()
        sockets = [
            FakeSocket(HELLO_RESPONSE),
            FakeSocket(b"-ERR unsupported command\r\n"),
        ]
        connection_factory = FakeConnectionFactory(sockets)

        with mock.patch.object(
            self.cli_main.socket,
            "create_connection",
            side_effect=connection_factory,
        ):
            exit_code = self.cli_main.main([], stdin=stdin, stdout=stdout, stderr=stderr)

        self.assertEqual(exit_code, defaults.CLI_EXIT_SUCCESS)
        self.assertEqual(stdout.getvalue(), "mini-redis> mini-redis> mini-redis> ")
        self.assertEqual(stderr.getvalue(), "ERR unsupported command\n")

    def test_repl_reports_invalid_quoted_input_and_keeps_prompt(self) -> None:
        stdin = io.StringIO('GET "unterminated\nquit\n')
        stdout = io.StringIO()
        stderr = io.StringIO()

        exit_code = self.cli_main.main([], stdin=stdin, stdout=stdout, stderr=stderr)

        self.assertEqual(exit_code, defaults.CLI_EXIT_SUCCESS)
        self.assertEqual(stdout.getvalue(), "mini-redis> mini-redis> ")
        self.assertIn("error:", stderr.getvalue())

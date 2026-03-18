import argparse
import socket
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, List, Optional, Sequence, TextIO, Union

if __package__ in (None, ""):
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from internal.config import defaults
from internal.config.runtime_config import RuntimeConfig

CRLF = b"\r\n"


class CliUsageError(Exception):
    pass


@dataclass(frozen=True)
class CliArguments:
    host: str
    port: int
    command: str
    command_arguments: List[str]


@dataclass(frozen=True)
class RespObject:
    kind: str
    value: object


class CliArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise CliUsageError(message)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = CliArgumentParser(prog="mini-redis-cli")
    parser.add_argument("--host", default=defaults.DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=defaults.DEFAULT_PORT)
    parser.add_argument("command", nargs="?")
    parser.add_argument("command_arguments", nargs=argparse.REMAINDER)
    return parser


def parse_cli_arguments(argv: Optional[Sequence[str]] = None) -> CliArguments:
    parser = build_argument_parser()
    namespace = parser.parse_args(list(argv) if argv is not None else None)
    if not namespace.command:
        raise CliUsageError("command is required")
    if namespace.port <= 0 or namespace.port > 65535:
        raise CliUsageError("port must be between 1 and 65535")
    return CliArguments(
        host=namespace.host,
        port=namespace.port,
        command=namespace.command,
        command_arguments=list(namespace.command_arguments),
    )


def build_runtime_config(arguments: CliArguments) -> RuntimeConfig:
    return RuntimeConfig.default().with_connection_target(
        host=arguments.host,
        port=arguments.port,
    )


def encode_blob_string(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return b"$" + str(len(encoded)).encode("ascii") + CRLF + encoded + CRLF


def encode_number(value: int) -> bytes:
    return b":" + str(value).encode("ascii") + CRLF


def encode_array(items: Sequence[Union[str, int]]) -> bytes:
    payload = bytearray()
    payload.extend(b"*" + str(len(items)).encode("ascii") + CRLF)
    for item in items:
        if isinstance(item, int):
            payload.extend(encode_number(item))
            continue
        payload.extend(encode_blob_string(item))
    return bytes(payload)


def build_hello_frame() -> bytes:
    return encode_array(["HELLO", 3])


def build_command_frame(command: str, arguments: Sequence[str]) -> bytes:
    return encode_array([command, *arguments])


def read_line(stream: BinaryIO) -> bytes:
    line = stream.readline()
    if not line:
        raise ConnectionError("server closed the connection")
    if not line.endswith(CRLF):
        raise ConnectionError("received an incomplete RESP line")
    return line[:-2]


def read_exact(stream: BinaryIO, size: int) -> bytes:
    data = stream.read(size)
    if data is None or len(data) != size:
        raise ConnectionError("received an incomplete RESP payload")
    return data


def read_null(stream: BinaryIO) -> RespObject:
    if read_line(stream) != b"":
        raise ConnectionError("invalid RESP null payload")
    return RespObject(kind="null", value=None)


def materialize_response_value(response: RespObject) -> object:
    if response.kind in {"simple_string", "blob_string", "number"}:
        return response.value
    if response.kind == "null":
        return None
    if response.kind == "map":
        return response.value
    return response.value


def read_response(stream: BinaryIO) -> RespObject:
    prefix = stream.read(1)
    if not prefix:
        raise ConnectionError("server closed the connection")

    if prefix == b"+":
        return RespObject(kind="simple_string", value=read_line(stream).decode("utf-8"))
    if prefix == b"-":
        message = read_line(stream).decode("utf-8")
        if message.startswith("ERR "):
            message = message[4:]
        return RespObject(kind="error", value=message)
    if prefix == b":":
        return RespObject(kind="number", value=int(read_line(stream).decode("ascii")))
    if prefix == b"_":
        return read_null(stream)
    if prefix == b"$":
        size = int(read_line(stream).decode("ascii"))
        if size < 0:
            return RespObject(kind="null", value=None)
        value = read_exact(stream, size).decode("utf-8")
        if read_line(stream) != b"":
            raise ConnectionError("invalid RESP blob string terminator")
        return RespObject(kind="blob_string", value=value)
    if prefix == b"%":
        item_count = int(read_line(stream).decode("ascii"))
        value = {}
        for _ in range(item_count):
            key = read_response(stream)
            item = read_response(stream)
            value[str(materialize_response_value(key))] = materialize_response_value(item)
        return RespObject(kind="map", value=value)

    raise ConnectionError(f"unsupported RESP type prefix: {prefix!r}")


def render_response(response: RespObject) -> str:
    if response.kind in {"simple_string", "blob_string", "number"}:
        return str(response.value)
    if response.kind == "null":
        return "(nil)"
    if response.kind == "map":
        lines = []
        for key, value in response.value.items():
            if value is None:
                lines.append(f"{key}: (nil)")
                continue
            lines.append(f"{key}: {value}")
        return "\n".join(lines)
    if response.kind == "error":
        return render_error(response)
    raise ValueError(f"unsupported response kind: {response.kind}")


def render_error(response: RespObject) -> str:
    message = str(response.value)
    if message.startswith("ERR "):
        return message
    return f"ERR {message}"


def execute_request(
    config: RuntimeConfig,
    request_frame: bytes,
) -> RespObject:
    client_socket = socket.create_connection(
        (config.host, config.port),
        timeout=config.connect_timeout_seconds,
    )

    with client_socket:
        client_socket.settimeout(
            max(config.read_timeout_seconds, config.write_timeout_seconds)
        )
        stream = client_socket.makefile("rb")
        try:
            client_socket.sendall(request_frame)
            return read_response(stream)
        finally:
            stream.close()


def execute_command(
    config: RuntimeConfig,
    command: str,
    command_arguments: Sequence[str],
) -> RespObject:
    hello_response = execute_request(config=config, request_frame=build_hello_frame())
    if hello_response.kind == "error":
        return hello_response

    return execute_request(
        config=config,
        request_frame=build_command_frame(command, command_arguments),
    )


def main(
    argv: Optional[Sequence[str]] = None,
    stdout: Optional[TextIO] = None,
    stderr: Optional[TextIO] = None,
) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr

    try:
        arguments = parse_cli_arguments(argv)
    except CliUsageError as error:
        parser = build_argument_parser()
        stderr.write(parser.format_usage())
        stderr.write(f"error: {error}\n")
        return defaults.CLI_EXIT_USAGE_ERROR

    try:
        response = execute_command(
            config=build_runtime_config(arguments),
            command=arguments.command,
            command_arguments=arguments.command_arguments,
        )
    except (ConnectionError, OSError, socket.timeout) as error:
        stderr.write(f"connection error: {error}\n")
        return defaults.CLI_EXIT_CONNECTION_ERROR

    if response.kind == "error":
        stderr.write(f"{render_error(response)}\n")
        return defaults.CLI_EXIT_SERVER_ERROR

    stdout.write(f"{render_response(response)}\n")
    return defaults.CLI_EXIT_SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())

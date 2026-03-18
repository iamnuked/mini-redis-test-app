from internal.command.command import Command
from internal.protocol.resp.protocol_handler import ProtocolHandler
from internal.protocol.resp.types import RespMap, RespSimpleError


def test_handle_returns_immediate_response_for_hello() -> None:
    handler = ProtocolHandler()

    result = handler.handle(b"*2\r\n$5\r\nHELLO\r\n:3\r\n")

    assert result.command is None
    assert isinstance(result.response, RespMap)
    assert result.has_immediate_response() is True


def test_handle_returns_command_for_non_hello_request() -> None:
    handler = ProtocolHandler()

    result = handler.handle(b"*2\r\n$3\r\nGET\r\n$3\r\nkey\r\n")

    assert result.response is None
    assert result.command == Command(name="GET", arguments=("key",))
    assert result.has_immediate_response() is False


def test_handle_accepts_variadic_command() -> None:
    handler = ProtocolHandler()

    result = handler.handle(b"*4\r\n$5\r\nLPUSH\r\n$3\r\nkey\r\n$1\r\na\r\n$1\r\nb\r\n")

    assert result.command == Command(name="LPUSH", arguments=("key", "a", "b"))


def test_handle_with_error_response_converts_protocol_failures() -> None:
    handler = ProtocolHandler()

    result = handler.handle_with_error_response(b"+PING\r\n")

    assert result.command is None
    assert result.response == RespSimpleError(message="protocol error")


def test_handle_with_error_response_converts_validation_failures() -> None:
    handler = ProtocolHandler()

    result = handler.handle_with_error_response(b"*2\r\n$6\r\nEXPIRE\r\n$3\r\nkey\r\n")

    assert result.command is None
    assert result.response == RespSimpleError(message="wrong number of arguments")

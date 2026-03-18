import pytest

from internal.command.errors import CommandParseError
from internal.command.parser import CommandParser
from internal.protocol.resp.messages import ERR_EMPTY_COMMAND, ERR_PROTOCOL_ERROR
from internal.protocol.resp.types import RespArray, RespBlobString, RespNull, RespNumber, RespSimpleString


def test_parse_normalizes_command_name_and_arguments() -> None:
    parser = CommandParser()

    command = parser.parse(
        RespArray(
            items=(
                RespBlobString(value="set"),
                RespBlobString(value="mykey"),
                RespSimpleString(value="value"),
            )
        )
    )

    assert command.name == "SET"
    assert command.arguments == ("mykey", "value")


def test_parse_accepts_number_argument() -> None:
    parser = CommandParser()

    command = parser.parse(
        RespArray(
            items=(
                RespSimpleString(value="hello"),
                RespNumber(value=3),
            )
        )
    )

    assert command.name == "HELLO"
    assert command.arguments == ("3",)


def test_parse_rejects_empty_command() -> None:
    parser = CommandParser()

    with pytest.raises(CommandParseError, match=ERR_EMPTY_COMMAND):
        parser.parse(RespArray(items=()))


def test_parse_rejects_unsupported_resp_item_type() -> None:
    parser = CommandParser()

    with pytest.raises(CommandParseError, match=ERR_PROTOCOL_ERROR):
        parser.parse(RespArray(items=(RespNull(),)))

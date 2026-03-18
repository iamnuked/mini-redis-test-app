import pytest

from internal.command.errors import CommandParseError
from internal.protocol.resp.messages import ERR_PROTOCOL_ERROR
from internal.protocol.resp.request_decoder import RespRequestDecoder
from internal.protocol.resp.types import RespArray, RespBlobString, RespNumber


def test_decode_hello_request_array() -> None:
    decoder = RespRequestDecoder()

    value = decoder.decode(b"*2\r\n$5\r\nHELLO\r\n:3\r\n")

    assert value == RespArray(
        items=(
            RespBlobString(value="HELLO"),
            RespNumber(value=3),
        )
    )


def test_decode_set_request_array() -> None:
    decoder = RespRequestDecoder()

    value = decoder.decode(b"*3\r\n$3\r\nSET\r\n$3\r\nkey\r\n$5\r\nvalue\r\n")

    assert value == RespArray(
        items=(
            RespBlobString(value="SET"),
            RespBlobString(value="key"),
            RespBlobString(value="value"),
        )
    )


def test_decode_rejects_non_array_top_level_request() -> None:
    decoder = RespRequestDecoder()

    with pytest.raises(CommandParseError, match=ERR_PROTOCOL_ERROR):
        decoder.decode(b"+PING\r\n")


def test_decode_rejects_malformed_blob_string() -> None:
    decoder = RespRequestDecoder()

    with pytest.raises(CommandParseError, match=ERR_PROTOCOL_ERROR):
        decoder.decode(b"*1\r\n$3\r\nSE\r\n")

from internal.protocol.resp.response_encoder import RespResponseEncoder
from internal.protocol.resp.types import (
    RespArray,
    RespBoolean,
    RespBlobString,
    RespMap,
    RespNull,
    RespNumber,
    RespSimpleError,
    RespSimpleString,
)


def test_encode_simple_string() -> None:
    encoder = RespResponseEncoder()

    assert encoder.encode(RespSimpleString(value="OK")) == b"+OK\r\n"


def test_encode_blob_string() -> None:
    encoder = RespResponseEncoder()

    assert encoder.encode(RespBlobString(value="hello")) == b"$5\r\nhello\r\n"


def test_encode_number() -> None:
    encoder = RespResponseEncoder()

    assert encoder.encode(RespNumber(value=3)) == b":3\r\n"


def test_encode_null() -> None:
    encoder = RespResponseEncoder()

    assert encoder.encode(RespNull()) == b"_\r\n"


def test_encode_null_in_resp2() -> None:
    encoder = RespResponseEncoder()

    assert encoder.encode(RespNull(), protocol_version=2) == b"$-1\r\n"


def test_encode_simple_error() -> None:
    encoder = RespResponseEncoder()

    assert encoder.encode(RespSimpleError(message="wrong number of arguments")) == (
        b"-ERR wrong number of arguments\r\n"
    )


def test_encode_map() -> None:
    encoder = RespResponseEncoder()

    value = RespMap(
        entries=(
            (RespSimpleString(value="server"), RespSimpleString(value="mini-redis")),
            (RespSimpleString(value="proto"), RespNumber(value=3)),
        )
    )

    assert encoder.encode(value) == b"%2\r\n+server\r\n+mini-redis\r\n+proto\r\n:3\r\n"


def test_encode_map_in_resp2_as_flat_array() -> None:
    encoder = RespResponseEncoder()

    value = RespMap(
        entries=(
            (RespBlobString(value="field"), RespBlobString(value="value")),
        )
    )

    assert encoder.encode(value, protocol_version=2) == (
        b"*2\r\n$5\r\nfield\r\n$5\r\nvalue\r\n"
    )


def test_encode_array() -> None:
    encoder = RespResponseEncoder()

    value = RespArray(
        items=(
            RespBlobString(value="a"),
            RespBlobString(value="b"),
        )
    )

    assert encoder.encode(value) == b"*2\r\n$1\r\na\r\n$1\r\nb\r\n"


def test_encode_boolean_in_resp2_as_number() -> None:
    encoder = RespResponseEncoder()

    assert encoder.encode(RespBoolean(value=True), protocol_version=2) == b":1\r\n"

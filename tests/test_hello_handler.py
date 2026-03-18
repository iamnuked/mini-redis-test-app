from internal.protocol.resp.hello_handler import HelloHandler
from internal.protocol.resp.messages import ERR_UNSUPPORTED_PROTOCOL_VERSION
from internal.protocol.resp.types import RespMap, RespNumber, RespSimpleError, RespSimpleString


def test_handle_returns_server_metadata_for_resp3() -> None:
    handler = HelloHandler()

    response = handler.handle(3)

    assert response == RespMap(
        entries=(
            (RespSimpleString(value="server"), RespSimpleString(value="mini-redis")),
            (RespSimpleString(value="version"), RespSimpleString(value="1.0")),
            (RespSimpleString(value="proto"), RespNumber(value=3)),
        )
    )


def test_handle_returns_error_for_unsupported_version() -> None:
    handler = HelloHandler()

    response = handler.handle(2)

    assert response == RespSimpleError(message=ERR_UNSUPPORTED_PROTOCOL_VERSION)

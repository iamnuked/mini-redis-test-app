from internal.protocol.resp.messages import ERR_UNSUPPORTED_PROTOCOL_VERSION
from internal.protocol.resp.types import RespMap, RespNumber, RespSimpleError, RespSimpleString, RespValue


class HelloHandler:
    def handle(self, version: int) -> RespValue:
        if version != 3:
            return RespSimpleError(message=ERR_UNSUPPORTED_PROTOCOL_VERSION)

        return RespMap(
            entries=(
                (RespSimpleString(value="server"), RespSimpleString(value="mini-redis")),
                (RespSimpleString(value="version"), RespSimpleString(value="1.0")),
                (RespSimpleString(value="proto"), RespNumber(value=3)),
            ),
        )

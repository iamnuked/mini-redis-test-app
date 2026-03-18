from internal.protocol.resp.types import RespValue


class HelloHandler:
    def handle(self, version: int) -> RespValue:
        if version != 3:
            return RespValue(kind="error", value="unsupported protocol version")
        return RespValue(
            kind="map",
            value={
                "server": "mini-redis",
                "version": "1.0",
                "proto": 3,
            },
        )

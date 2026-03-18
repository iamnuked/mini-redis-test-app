from internal.protocol.resp.types import RespValue


class RespResponseEncoder:
    def encode(self, value: RespValue) -> bytes:
        raise NotImplementedError("RESP3 response encoding is not implemented yet")

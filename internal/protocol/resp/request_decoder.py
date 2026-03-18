from internal.protocol.resp.types import RespValue


class RespRequestDecoder:
    def decode(self, data: bytes) -> RespValue:
        raise NotImplementedError("RESP3 request decoding is not implemented yet")

from internal.protocol.resp.messages import RESP_ERR_PREFIX
from internal.protocol.resp.types import (
    RespArray,
    RespBlobString,
    RespMap,
    RespNull,
    RespNumber,
    RespSimpleError,
    RespSimpleString,
    RespValue,
)


class RespResponseEncoder:
    def encode(self, value: RespValue) -> bytes:
        if isinstance(value, RespSimpleString):
            return f"+{value.value}\r\n".encode("utf-8")

        if isinstance(value, RespBlobString):
            payload = value.value.encode("utf-8")
            return b"$" + str(len(payload)).encode("utf-8") + b"\r\n" + payload + b"\r\n"

        if isinstance(value, RespNumber):
            return f":{value.value}\r\n".encode("utf-8")

        if isinstance(value, RespNull):
            return b"_\r\n"

        if isinstance(value, RespSimpleError):
            return f"-{RESP_ERR_PREFIX} {value.message}\r\n".encode("utf-8")

        if isinstance(value, RespArray):
            encoded_items = b"".join(self.encode(item) for item in value.items)
            return b"*" + str(len(value.items)).encode("utf-8") + b"\r\n" + encoded_items

        if isinstance(value, RespMap):
            encoded_entries = []
            for key, entry_value in value.entries:
                encoded_entries.append(self.encode(key))
                encoded_entries.append(self.encode(entry_value))
            return (
                b"%"
                + str(len(value.entries)).encode("utf-8")
                + b"\r\n"
                + b"".join(encoded_entries)
            )

        raise TypeError(f"unsupported RESP value: {type(value)!r}")

from internal.protocol.resp.messages import RESP_ERR_PREFIX
from internal.protocol.resp.types import (
    RespArray,
    RespBoolean,
    RespBlobString,
    RespMap,
    RespNull,
    RespNumber,
    RespSimpleError,
    RespSimpleString,
    RespValue,
)


class RespResponseEncoder:
    def encode(self, value: RespValue, protocol_version: int = 3) -> bytes:
        if isinstance(value, RespSimpleString):
            return f"+{value.value}\r\n".encode("utf-8")

        if isinstance(value, RespBlobString):
            payload = value.value.encode("utf-8")
            return b"$" + str(len(payload)).encode("utf-8") + b"\r\n" + payload + b"\r\n"

        if isinstance(value, RespNumber):
            return f":{value.value}\r\n".encode("utf-8")

        if isinstance(value, RespNull):
            if protocol_version == 2:
                return b"$-1\r\n"
            return b"_\r\n"

        if isinstance(value, RespSimpleError):
            return f"-{RESP_ERR_PREFIX} {value.message}\r\n".encode("utf-8")

        if isinstance(value, RespBoolean):
            if protocol_version == 2:
                return f":{1 if value.value else 0}\r\n".encode("utf-8")
            return b"#t\r\n" if value.value else b"#f\r\n"

        if isinstance(value, RespArray):
            encoded_items = b"".join(self.encode(item, protocol_version) for item in value.items)
            return b"*" + str(len(value.items)).encode("utf-8") + b"\r\n" + encoded_items

        if isinstance(value, RespMap):
            if protocol_version == 2:
                flattened_items: list[RespValue] = []
                for key, entry_value in value.entries:
                    flattened_items.append(key)
                    flattened_items.append(entry_value)
                return self.encode(RespArray(items=tuple(flattened_items)), protocol_version=2)
            encoded_entries = []
            for key, entry_value in value.entries:
                encoded_entries.append(self.encode(key, protocol_version))
                encoded_entries.append(self.encode(entry_value, protocol_version))
            return (
                b"%"
                + str(len(value.entries)).encode("utf-8")
                + b"\r\n"
                + b"".join(encoded_entries)
            )

        raise TypeError(f"unsupported RESP value: {type(value)!r}")

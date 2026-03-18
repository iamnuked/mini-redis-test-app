from __future__ import annotations

from internal.command.errors import CommandParseError
from internal.protocol.resp.messages import ERR_PROTOCOL_ERROR
from internal.protocol.resp.types import (
    RespArray,
    RespBlobString,
    RespNumber,
    RespSimpleString,
    RespValue,
)


class RespRequestDecoder:
    def decode(self, data: bytes) -> RespValue:
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise CommandParseError(ERR_PROTOCOL_ERROR) from exc

        value, next_index = self._decode_value(text, 0)
        if not isinstance(value, RespArray):
            raise CommandParseError(ERR_PROTOCOL_ERROR)
        if next_index != len(text):
            raise CommandParseError(ERR_PROTOCOL_ERROR)
        return value

    def _decode_value(self, data: str, index: int) -> tuple[RespValue, int]:
        if index >= len(data):
            raise CommandParseError(ERR_PROTOCOL_ERROR)

        prefix = data[index]
        if prefix == "*":
            return self._decode_array(data, index)
        if prefix == "$":
            return self._decode_blob_string(data, index)
        if prefix == "+":
            return self._decode_simple_string(data, index)
        if prefix == ":":
            return self._decode_number(data, index)

        raise CommandParseError(ERR_PROTOCOL_ERROR)

    def _decode_array(self, data: str, index: int) -> tuple[RespArray, int]:
        count_text, cursor = self._read_line(data, index + 1)
        try:
            count = int(count_text)
        except ValueError as exc:
            raise CommandParseError(ERR_PROTOCOL_ERROR) from exc
        if count < 0:
            raise CommandParseError(ERR_PROTOCOL_ERROR)

        items = []
        for _ in range(count):
            item, cursor = self._decode_value(data, cursor)
            items.append(item)

        return RespArray(items=tuple(items)), cursor

    def _decode_blob_string(self, data: str, index: int) -> tuple[RespBlobString, int]:
        length_text, cursor = self._read_line(data, index + 1)
        try:
            length = int(length_text)
        except ValueError as exc:
            raise CommandParseError(ERR_PROTOCOL_ERROR) from exc
        if length < 0:
            raise CommandParseError(ERR_PROTOCOL_ERROR)

        end_index = cursor + length
        if end_index + 2 > len(data) or data[end_index : end_index + 2] != "\r\n":
            raise CommandParseError(ERR_PROTOCOL_ERROR)

        return RespBlobString(value=data[cursor:end_index]), end_index + 2

    def _decode_simple_string(
        self,
        data: str,
        index: int,
    ) -> tuple[RespSimpleString, int]:
        value, cursor = self._read_line(data, index + 1)
        return RespSimpleString(value=value), cursor

    def _decode_number(self, data: str, index: int) -> tuple[RespNumber, int]:
        number_text, cursor = self._read_line(data, index + 1)
        try:
            number = int(number_text)
        except ValueError as exc:
            raise CommandParseError(ERR_PROTOCOL_ERROR) from exc

        return RespNumber(value=number), cursor

    def _read_line(self, data: str, start: int) -> tuple[str, int]:
        end_index = data.find("\r\n", start)
        if end_index == -1:
            raise CommandParseError(ERR_PROTOCOL_ERROR)
        return data[start:end_index], end_index + 2

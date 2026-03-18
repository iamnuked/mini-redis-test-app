from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias


@dataclass(frozen=True)
class RespSimpleString:
    value: str


@dataclass(frozen=True)
class RespBlobString:
    value: str


@dataclass(frozen=True)
class RespNumber:
    value: int


@dataclass(frozen=True)
class RespNull:
    pass


@dataclass(frozen=True)
class RespSimpleError:
    message: str


@dataclass(frozen=True)
class RespArray:
    items: tuple["RespValue", ...]


@dataclass(frozen=True)
class RespMap:
    entries: tuple[tuple["RespValue", "RespValue"], ...]


@dataclass(frozen=True)
class RespBoolean:
    value: bool


RespValue: TypeAlias = (
    RespSimpleString
    | RespBlobString
    | RespNumber
    | RespNull
    | RespSimpleError
    | RespArray
    | RespMap
    | RespBoolean
)

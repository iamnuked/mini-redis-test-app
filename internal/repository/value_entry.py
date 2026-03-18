from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ValueType(str, Enum):
    STRING = "string"
    HASH = "hash"
    LIST = "list"
    SET = "set"
    ZSET = "zset"


StoreValue = str | dict[str, str] | list[str] | set[str] | dict[str, float]


@dataclass
class ValueEntry:
    value_type: ValueType
    value: StoreValue

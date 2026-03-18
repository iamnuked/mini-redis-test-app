from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import Iterable
from typing import Protocol


class ArenaRepository(Protocol):
    def write(self, key: str, value: str) -> str:
        ...

    def read(self, key: str) -> str | None:
        ...

    def delete(self, key: str) -> bool:
        ...

    def delete_many(self, keys: Iterable[str]) -> None:
        ...

    def clear(self) -> None:
        ...

    def seed(self, documents: dict[str, str]) -> None:
        ...

    def healthcheck(self) -> dict[str, str]:
        ...


@dataclass
class MongoRepositorySettings:
    backend: str = "inmemory"
    uri: str = "mongodb://127.0.0.1:27017"
    db_name: str = "arena"
    collection_name: str = "documents"
    server_selection_timeout_ms: int = 1000

    @classmethod
    def from_env(
        cls,
        *,
        default_backend: str = "inmemory",
        default_db_name: str = "arena",
    ) -> "MongoRepositorySettings":
        return cls(
            backend=os.getenv("ARENA_MONGO_BACKEND", default_backend),
            uri=os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017"),
            db_name=os.getenv("MONGO_DB_NAME", default_db_name),
            collection_name=os.getenv("MONGO_COLLECTION_NAME", "documents"),
            server_selection_timeout_ms=int(
                os.getenv("MONGO_SERVER_SELECTION_TIMEOUT_MS", "1000")
            ),
        )


@dataclass
class InMemoryMongoRepository:
    name: str
    _documents: dict[str, str] = field(default_factory=dict)

    def write(self, key: str, value: str) -> str:
        created = key not in self._documents
        self._documents[key] = value
        return "created" if created else "updated"

    def read(self, key: str) -> str | None:
        return self._documents.get(key)

    def delete(self, key: str) -> bool:
        if key not in self._documents:
            return False
        del self._documents[key]
        return True

    def delete_many(self, keys: Iterable[str]) -> None:
        for key in keys:
            self.delete(key)

    def clear(self) -> None:
        self._documents.clear()

    def seed(self, documents: dict[str, str]) -> None:
        self._documents.update(documents)

    def healthcheck(self) -> dict[str, str]:
        return {"backend": "inmemory", "name": self.name, "status": "ok"}


@dataclass
class PyMongoArenaRepository:
    settings: MongoRepositorySettings

    def __post_init__(self) -> None:
        self._pymongo = self._load_pymongo_module()
        self._client = self._pymongo.MongoClient(
            self.settings.uri,
            serverSelectionTimeoutMS=self.settings.server_selection_timeout_ms,
        )
        self._collection = self._client[self.settings.db_name][self.settings.collection_name]

    def _load_pymongo_module(self):
        try:
            import pymongo
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "pymongo package is required for ARENA_MONGO_BACKEND=pymongo"
            ) from exc
        return pymongo

    def write(self, key: str, value: str) -> str:
        created = self.read(key) is None
        self._collection.replace_one(
            {"_id": key},
            {"_id": key, "value": value},
            upsert=True,
        )
        return "created" if created else "updated"

    def read(self, key: str) -> str | None:
        document = self._collection.find_one({"_id": key})
        if document is None:
            return None
        return document.get("value")

    def delete(self, key: str) -> bool:
        result = self._collection.delete_one({"_id": key})
        return bool(result.deleted_count)

    def delete_many(self, keys: Iterable[str]) -> None:
        key_list = list(keys)
        if not key_list:
            return
        self._collection.delete_many({"_id": {"$in": key_list}})

    def clear(self) -> None:
        self._collection.delete_many({})

    def seed(self, documents: dict[str, str]) -> None:
        if not documents:
            return
        operations = [
            self._pymongo.ReplaceOne(
                {"_id": key},
                {"_id": key, "value": value},
                upsert=True,
            )
            for key, value in documents.items()
        ]
        self._collection.bulk_write(operations, ordered=False)

    def healthcheck(self) -> dict[str, str]:
        self._client.admin.command("ping")
        return {
            "backend": "pymongo",
            "db_name": self.settings.db_name,
            "collection_name": self.settings.collection_name,
            "status": "ok",
        }


def build_arena_repository(settings: MongoRepositorySettings) -> ArenaRepository:
    if settings.backend == "pymongo":
        return PyMongoArenaRepository(settings=settings)
    if settings.backend == "inmemory":
        return InMemoryMongoRepository(name=settings.db_name)
    raise ValueError(f"Unsupported ARENA_MONGO_BACKEND: {settings.backend}")

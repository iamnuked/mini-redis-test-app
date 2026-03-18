from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class MongoBaselineError(Exception):
    pass


class MongoBaselineClient:
    def __init__(
        self,
        uri: str,
        db_name: str,
        collection_name: str,
        seed_file: str,
        connect_timeout_ms: int = 1000,
    ) -> None:
        self._uri = uri
        self._db_name = db_name
        self._collection_name = collection_name
        self._seed_file = Path(seed_file)
        self._connect_timeout_ms = connect_timeout_ms
        self._client: Any | None = None
        self._collection: Any | None = None
        self._seeded = False

    def health_check(self) -> bool:
        try:
            self._get_collection().database.command("ping")
        except Exception as exc:
            raise MongoBaselineError(str(exc)) from exc
        return True

    def fetch_detail(self, record_id: str) -> dict[str, str]:
        collection = self._get_collection()
        document = collection.find_one({"record_id": record_id}, {"_id": 0})
        if document is None:
            fallback_document = {
                "record_id": record_id,
                "title": f"Detail {record_id}",
                "body": f"Body for {record_id}",
            }
            collection.update_one(
                {"record_id": record_id},
                {"$setOnInsert": fallback_document},
                upsert=True,
            )
            document = fallback_document
        return {
            "id": str(document["record_id"]),
            "title": str(document.get("title", "")),
            "body": str(document.get("body", "")),
        }

    def seed(self) -> int:
        collection = self._get_collection()
        documents = _read_seed_documents(self._seed_file)
        upserted_count = 0
        for document in documents:
            result = collection.update_one(
                {"record_id": document["record_id"]},
                {"$setOnInsert": document},
                upsert=True,
            )
            if result.upserted_id is not None:
                upserted_count += 1
        self._seeded = True
        return upserted_count

    def _get_collection(self) -> Any:
        if self._collection is not None:
            return self._collection

        try:
            from pymongo import MongoClient
        except ModuleNotFoundError as exc:
            raise MongoBaselineError(
                "pymongo is not installed. Activate .venv and install requirements.txt first."
            ) from exc

        try:
            self._client = MongoClient(self._uri, serverSelectionTimeoutMS=self._connect_timeout_ms)
            database = self._client[self._db_name]
            collection = database[self._collection_name]
            database.command("ping")
            collection.create_index("record_id", unique=True)
            self._collection = collection
            if not self._seeded:
                self.seed()
            return self._collection
        except Exception as exc:
            raise MongoBaselineError(str(exc)) from exc


def _read_seed_documents(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise MongoBaselineError(f"seed file not found: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise MongoBaselineError("seed file must contain a JSON array")
    documents: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise MongoBaselineError("seed documents must be JSON objects")
        record_id = item.get("record_id")
        if not isinstance(record_id, str) or not record_id:
            raise MongoBaselineError("each seed document must have a non-empty string record_id")
        documents.append(
            {
                "record_id": record_id,
                "title": str(item.get("title", f"Detail {record_id}")),
                "body": str(item.get("body", f"Body for {record_id}")),
            }
        )
    return documents

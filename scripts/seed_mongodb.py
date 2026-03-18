from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.adapters.mongodb_baseline import MongoBaselineClient
from app.api.config import ControllerSettings


def main() -> None:
    settings = ControllerSettings.from_env()
    client = MongoBaselineClient(
        uri=settings.mongodb_uri,
        db_name=settings.mongodb_db_name,
        collection_name=settings.mongodb_collection,
        seed_file=settings.mongodb_seed_file,
        connect_timeout_ms=settings.mongodb_connect_timeout_ms,
    )
    inserted = client.seed()
    print(
        f"mongodb seed completed: db={settings.mongodb_db_name} "
        f"collection={settings.mongodb_collection} inserted={inserted}"
    )


if __name__ == "__main__":
    main()

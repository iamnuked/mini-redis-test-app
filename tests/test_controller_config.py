from __future__ import annotations

import json
import os
import unittest
from tempfile import TemporaryDirectory

from app.api.config import ControllerSettings


class ControllerSettingsTest(unittest.TestCase):
    def test_from_env_reads_json_settings_file(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            path = os.path.join(tmp_dir, "settings.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "baseline_backend": "mongodb",
                        "mongodb_uri": "mongodb://127.0.0.1:27017",
                        "mongodb_db_name": "bench",
                        "mongodb_collection": "details",
                        "mongodb_seed_file": "data/mongodb/detail_page_seed.json",
                        "mongodb_connect_timeout_ms": 2500,
                    },
                    handle,
                )

            previous = os.environ.get("APP_SETTINGS_FILE")
            os.environ["APP_SETTINGS_FILE"] = path
            try:
                settings = ControllerSettings.from_env()
            finally:
                if previous is None:
                    os.environ.pop("APP_SETTINGS_FILE", None)
                else:
                    os.environ["APP_SETTINGS_FILE"] = previous

        self.assertEqual(settings.baseline_backend, "mongodb")
        self.assertEqual(settings.mongodb_db_name, "bench")
        self.assertEqual(settings.mongodb_collection, "details")
        self.assertEqual(settings.mongodb_connect_timeout_ms, 2500)


if __name__ == "__main__":
    unittest.main()

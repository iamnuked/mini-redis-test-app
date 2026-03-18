import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from internal.arena.lane_a.api.app import create_app as create_lane_a_app
from internal.arena.lane_b.api.app import create_app as create_lane_b_app


class LaneAApiTests(unittest.TestCase):
    def test_lane_a_execute_seed_reset_and_health(self) -> None:
        with patch.dict(
            os.environ,
            {
                "ARENA_MONGO_BACKEND": "inmemory",
                "ARENA_REDIS_BACKEND": "inmemory",
                "MONGO_DB_NAME": "lane_a_test",
            },
            clear=False,
        ):
            client = TestClient(create_lane_a_app())

            health_response = client.get("/health")
            self.assertEqual(health_response.status_code, 200)
            self.assertEqual(health_response.json()["status"], "ok")
            self.assertEqual(health_response.json()["redis"]["status"], "ok")

            seed_response = client.post(
                "/seed",
                json={
                    "documents": {"user:1": '{"name":"kim"}'},
                    "warm_cache": True,
                    "ttl_enabled": True,
                },
            )
            self.assertEqual(seed_response.status_code, 200)

            get_response = client.post(
                "/execute",
                json={
                    "request_id": "req-a1",
                    "mode": "manual",
                    "command": "GET",
                    "key": "user:1",
                    "value": None,
                    "ttl_enabled": True,
                },
            )
            payload = get_response.json()
            self.assertEqual(get_response.status_code, 200)
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["lane"], "redis_db")
            self.assertIn("redis_hit", payload["path"])
            self.assertIn("metrics", payload)
            self.assertEqual(payload["answer_text"], '{"name":"kim"}')
            self.assertEqual(payload["answer_kind"], "value")

            reset_response = client.post("/reset", json={"keys": ["user:1"]})
            self.assertEqual(reset_response.status_code, 200)

            miss_response = client.post(
                "/execute",
                json={
                    "request_id": "req-a2",
                    "mode": "manual",
                    "command": "GET",
                    "key": "user:1",
                    "value": None,
                    "ttl_enabled": True,
                },
            )
            self.assertEqual(miss_response.status_code, 200)
            self.assertIn("Mongo document missing", miss_response.json()["storage_changes"])


class LaneBApiTests(unittest.TestCase):
    def test_lane_b_execute_seed_reset_and_health(self) -> None:
        with patch.dict(
            os.environ,
            {
                "ARENA_MONGO_BACKEND": "inmemory",
                "MONGO_DB_NAME": "lane_b_test",
            },
            clear=False,
        ):
            client = TestClient(create_lane_b_app())

            health_response = client.get("/health")
            self.assertEqual(health_response.status_code, 200)
            self.assertEqual(health_response.json()["status"], "ok")
            self.assertEqual(health_response.json()["mongo"]["status"], "ok")

            seed_response = client.post(
                "/seed",
                json={"documents": {"user:2": '{"name":"lee"}'}},
            )
            self.assertEqual(seed_response.status_code, 200)

            get_response = client.post(
                "/execute",
                json={
                    "request_id": "req-b1",
                    "mode": "manual",
                    "command": "GET",
                    "key": "user:2",
                    "value": None,
                    "ttl_enabled": False,
                },
            )
            payload = get_response.json()
            self.assertEqual(get_response.status_code, 200)
            self.assertEqual(payload["lane"], "db_only")
            self.assertEqual(payload["path"], ["mongo_read"])
            self.assertEqual(payload["answer_text"], '{"name":"lee"}')
            self.assertEqual(payload["answer_kind"], "value")

            reset_response = client.post("/reset", json={"keys": ["user:2"]})
            self.assertEqual(reset_response.status_code, 200)

            miss_response = client.post(
                "/execute",
                json={
                    "request_id": "req-b2",
                    "mode": "manual",
                    "command": "GET",
                    "key": "user:2",
                    "value": None,
                    "ttl_enabled": False,
                },
            )
            self.assertEqual(miss_response.status_code, 200)
            self.assertIn("Mongo document missing", miss_response.json()["storage_changes"])

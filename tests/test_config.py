import unittest

from internal.config import defaults
from internal.config.runtime_config import RuntimeConfig


class RuntimeConfigTest(unittest.TestCase):
    def test_default_runtime_config_matches_documented_values(self) -> None:
        config = RuntimeConfig.default()

        self.assertEqual(config.host, defaults.DEFAULT_HOST)
        self.assertEqual(config.port, defaults.DEFAULT_PORT)
        self.assertEqual(
            config.connect_timeout_seconds,
            defaults.DEFAULT_CONNECT_TIMEOUT_SECONDS,
        )
        self.assertEqual(config.read_timeout_seconds, defaults.DEFAULT_READ_TIMEOUT_SECONDS)
        self.assertEqual(
            config.write_timeout_seconds,
            defaults.DEFAULT_WRITE_TIMEOUT_SECONDS,
        )
        self.assertEqual(config.idle_timeout_seconds, defaults.DEFAULT_IDLE_TIMEOUT_SECONDS)
        self.assertEqual(config.max_connections, defaults.DEFAULT_MAX_CONNECTIONS)
        self.assertEqual(
            config.max_request_size_bytes,
            defaults.DEFAULT_MAX_REQUEST_SIZE_BYTES,
        )
        self.assertEqual(config.max_array_items, defaults.DEFAULT_MAX_ARRAY_ITEMS)
        self.assertEqual(config.max_resp_depth, defaults.DEFAULT_MAX_RESP_DEPTH)
        self.assertEqual(config.max_blob_size_bytes, defaults.DEFAULT_MAX_BLOB_SIZE_BYTES)
        self.assertEqual(
            config.expiration_sweep_interval_seconds,
            defaults.DEFAULT_EXPIRATION_SWEEP_INTERVAL_SECONDS,
        )
        self.assertEqual(
            config.expiration_sweep_batch_size,
            defaults.DEFAULT_EXPIRATION_SWEEP_BATCH_SIZE,
        )
        self.assertEqual(
            config.expiration_sweep_enabled,
            defaults.DEFAULT_EXPIRATION_SWEEP_ENABLED,
        )
        self.assertEqual(config.log_level, defaults.DEFAULT_LOG_LEVEL)
        self.assertEqual(
            config.graceful_shutdown_seconds,
            defaults.DEFAULT_GRACEFUL_SHUTDOWN_SECONDS,
        )

    def test_with_connection_target_overrides_only_host_and_port(self) -> None:
        original = RuntimeConfig.default()

        updated = original.with_connection_target(host="localhost", port=6380)

        self.assertEqual(updated.host, "localhost")
        self.assertEqual(updated.port, 6380)
        self.assertEqual(
            updated.connect_timeout_seconds,
            original.connect_timeout_seconds,
        )
        self.assertEqual(updated.read_timeout_seconds, original.read_timeout_seconds)
        self.assertEqual(updated.log_level, original.log_level)

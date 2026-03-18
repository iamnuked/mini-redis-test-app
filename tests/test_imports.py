from internal.config.runtime_config import RuntimeConfig
from internal.server.server import MiniRedisServer


def test_runtime_config_default_can_be_created() -> None:
    config = RuntimeConfig.default()
    server = MiniRedisServer(config)
    assert server is not None

from __future__ import annotations

import os

from internal.config.runtime_config import RuntimeConfig
from internal.server.server import MiniRedisServer


def main() -> None:
    config = RuntimeConfig.default().with_connection_target(
        host=os.getenv("MINI_REDIS_SERVER_HOST", os.getenv("MINI_REDIS_HOST", "127.0.0.1")),
        port=int(os.getenv("MINI_REDIS_SERVER_PORT", os.getenv("MINI_REDIS_PORT", "6379"))),
    )
    server = MiniRedisServer(config)
    server.run()


if __name__ == "__main__":
    main()

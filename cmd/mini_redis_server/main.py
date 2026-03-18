from internal.config.runtime_config import RuntimeConfig
from internal.server.server import MiniRedisServer


def main() -> None:
    config = RuntimeConfig.default()
    server = MiniRedisServer(config)
    server.run()


if __name__ == "__main__":
    main()

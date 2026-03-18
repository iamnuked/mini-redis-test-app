from internal.config.runtime_config import RuntimeConfig


class MiniRedisServer:
    def __init__(self, config: RuntimeConfig) -> None:
        self._config = config

    def run(self) -> None:
        print(f"mini-redis server skeleton listening on {self._config.host}:{self._config.port}")

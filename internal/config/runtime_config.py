from dataclasses import dataclass, replace

from internal.config import defaults


@dataclass(frozen=True)
class RuntimeConfig:
    host: str
    port: int
    connect_timeout_seconds: int
    read_timeout_seconds: int
    write_timeout_seconds: int
    idle_timeout_seconds: int
    max_connections: int
    max_request_size_bytes: int
    max_array_items: int
    max_resp_depth: int
    max_blob_size_bytes: int
    expiration_sweep_interval_seconds: int
    expiration_sweep_batch_size: int
    expiration_sweep_enabled: bool
    log_level: str
    graceful_shutdown_seconds: int

    @classmethod
    def default(cls) -> "RuntimeConfig":
        return cls(
            host=defaults.DEFAULT_HOST,
            port=defaults.DEFAULT_PORT,
            connect_timeout_seconds=defaults.DEFAULT_CONNECT_TIMEOUT_SECONDS,
            read_timeout_seconds=defaults.DEFAULT_READ_TIMEOUT_SECONDS,
            write_timeout_seconds=defaults.DEFAULT_WRITE_TIMEOUT_SECONDS,
            idle_timeout_seconds=defaults.DEFAULT_IDLE_TIMEOUT_SECONDS,
            max_connections=defaults.DEFAULT_MAX_CONNECTIONS,
            max_request_size_bytes=defaults.DEFAULT_MAX_REQUEST_SIZE_BYTES,
            max_array_items=defaults.DEFAULT_MAX_ARRAY_ITEMS,
            max_resp_depth=defaults.DEFAULT_MAX_RESP_DEPTH,
            max_blob_size_bytes=defaults.DEFAULT_MAX_BLOB_SIZE_BYTES,
            expiration_sweep_interval_seconds=(
                defaults.DEFAULT_EXPIRATION_SWEEP_INTERVAL_SECONDS
            ),
            expiration_sweep_batch_size=defaults.DEFAULT_EXPIRATION_SWEEP_BATCH_SIZE,
            expiration_sweep_enabled=defaults.DEFAULT_EXPIRATION_SWEEP_ENABLED,
            log_level=defaults.DEFAULT_LOG_LEVEL,
            graceful_shutdown_seconds=defaults.DEFAULT_GRACEFUL_SHUTDOWN_SECONDS,
        )

    def with_connection_target(self, host: str, port: int) -> "RuntimeConfig":
        return replace(self, host=host, port=port)

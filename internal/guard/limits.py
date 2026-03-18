from dataclasses import dataclass


@dataclass(frozen=True)
class ResourceLimits:
    max_connections: int
    max_request_size_bytes: int
    max_array_items: int
    max_resp_depth: int
    max_blob_size_bytes: int

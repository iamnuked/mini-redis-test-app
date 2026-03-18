from internal.guard.limits import ResourceLimits


class ResourceGuard:
    def __init__(self, limits: ResourceLimits) -> None:
        self._limits = limits

    def validate_request_size(self, size_bytes: int) -> bool:
        return size_bytes <= self._limits.max_request_size_bytes

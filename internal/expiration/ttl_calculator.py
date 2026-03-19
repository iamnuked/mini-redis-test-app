from math import ceil


class TtlCalculator:
    def calculate_expires_at(self, now: float, ttl_seconds: float) -> float:
        return now + ttl_seconds

    def is_expired(self, now: float, expires_at: float) -> bool:
        return now >= expires_at

    def calculate_remaining_seconds(self, now: float, expires_at: float) -> int:
        return max(0, ceil(expires_at - now))

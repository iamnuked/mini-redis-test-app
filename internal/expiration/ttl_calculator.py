class TtlCalculator:
    def calculate_remaining_seconds(self, now: float, expires_at: float) -> int:
        return int(expires_at - now)

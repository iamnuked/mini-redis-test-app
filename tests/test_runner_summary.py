from __future__ import annotations

import unittest

from app.benchmark.runner import build_summary


class RunnerSummaryTest(unittest.TestCase):
    def test_build_summary_calculates_speedup_and_hit_rate(self) -> None:
        summary = build_summary(
            baseline_samples=[100.0, 120.0, 110.0],
            cache_samples=[20.0, 30.0, 25.0],
            reference_samples=[10.0, 11.0, 9.0],
            buckets=[0, 35, 60, 100],
            bucket_averages={0: 150.0, 35: 112.0, 60: 25.0, 100: 10.0},
            cache_hits=6,
            cache_total=10,
            db_only_count=3,
            redis_hit_count=6,
            redis_miss_count=4,
            fallback_count=0,
            error_count=1,
        )

        self.assertEqual(summary.db_avg_ms, 110.0)
        self.assertEqual(summary.redis_avg_ms, 25.0)
        self.assertEqual(summary.reference_avg_ms, 10.0)
        self.assertEqual(summary.speedup_ratio, 4.4)
        self.assertEqual(summary.break_even_hit_rate, 60)
        self.assertEqual(summary.cache_hit_rate, 60.0)
        self.assertEqual(summary.redis_miss_count, 4)
        self.assertEqual(summary.error_count, 1)


if __name__ == "__main__":
    unittest.main()

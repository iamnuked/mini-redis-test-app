from __future__ import annotations

import statistics
import time
from pathlib import Path

from app.adapters.baseline import BaselineClient
from app.adapters.mini_redis import MiniRedisClient, MiniRedisError
from app.benchmark.models import FlowEvent, RunConfig, RunRecord, RunSummary, utc_now_iso
from app.storage.run_store import RunStore


class BenchmarkRunner:
    def __init__(self, store: RunStore, baseline_client: BaselineClient, redis_client: MiniRedisClient) -> None:
        self._store = store
        self._baseline_client = baseline_client
        self._redis_client = redis_client

    def run(self, run_id: str) -> None:
        record = self._store.read_run(run_id)
        config = record.config
        record.status = "bootstrapping"
        record.started_at = utc_now_iso()
        record.updated_at = utc_now_iso()
        self._store.write_run(record)
        self._store.append_log(
            run_id,
            "INFO",
            "bootstrap",
            "benchmark started",
            {"scenario": config.scenario},
        )

        try:
            if not self._redis_client.health_check():
                raise MiniRedisError("mini-redis health check failed")
            self._store.append_log(run_id, "INFO", "bootstrap", "mini-redis health check passed")

            baseline_health_check = getattr(self._baseline_client, "health_check", None)
            if callable(baseline_health_check):
                if not baseline_health_check():
                    raise RuntimeError("baseline database health check failed")
                self._store.append_log(run_id, "INFO", "bootstrap", "baseline database health check passed")

            record.status = "warming_up"
            record.updated_at = utc_now_iso()
            self._store.write_run(record)
            warmup_count = min(3, config.iteration_count)
            self._store.append_log(
                run_id,
                "INFO",
                "warmup",
                "warmup started",
                {"warmup_count": warmup_count},
            )
            self._warmup(config)
            self._store.append_log(
                run_id,
                "INFO",
                "warmup",
                "warmup completed",
                {"warmup_count": warmup_count},
            )

            record.status = "running_baseline"
            record.updated_at = utc_now_iso()
            self._store.write_run(record)
            self._store.append_log(
                run_id,
                "INFO",
                "baseline_run",
                "baseline benchmark started",
                {"iteration_count": config.iteration_count},
            )
            baseline_samples = self._run_baseline(run_id, config)

            record.status = "running_cache"
            record.updated_at = utc_now_iso()
            self._store.write_run(record)
            self._store.append_log(
                run_id,
                "INFO",
                "cache_run",
                "cache benchmark started",
                {
                    "iteration_count": config.iteration_count,
                    "bucket_count": len(config.hit_rate_buckets),
                },
            )
            (
                cache_samples,
                cache_hits,
                cache_total,
                redis_miss_count,
                fallback_count,
                error_count,
                bucket_averages,
            ) = self._run_cache(run_id, config)

            reference_samples: list[float] = []
            if config.include_reference:
                record.status = "running_reference"
                record.updated_at = utc_now_iso()
                self._store.write_run(record)
                self._store.append_log(
                    run_id,
                    "INFO",
                    "reference_run",
                    "reference benchmark started",
                    {"iteration_count": config.iteration_count},
                )
                reference_samples = self._run_reference(run_id, config)

            record.status = "aggregating"
            record.updated_at = utc_now_iso()
            self._store.write_run(record)
            self._store.append_log(run_id, "INFO", "aggregation", "aggregation started")
            summary = build_summary(
                baseline_samples=baseline_samples,
                cache_samples=cache_samples,
                reference_samples=reference_samples,
                buckets=config.hit_rate_buckets,
                bucket_averages=bucket_averages,
                cache_hits=cache_hits,
                cache_total=cache_total,
                db_only_count=len(baseline_samples),
                redis_hit_count=cache_hits,
                redis_miss_count=redis_miss_count,
                fallback_count=fallback_count,
                error_count=error_count,
            )

            record.status = "completed"
            record.updated_at = utc_now_iso()
            record.finished_at = utc_now_iso()
            record.summary = summary
            record.mini_redis_commit = read_git_head(Path(".tmp/mini-redis-dev"))
            record.app_commit = read_git_head(Path("."))
            self._store.write_run(record)
            self._store.append_log(
                run_id,
                "INFO",
                "aggregation",
                "aggregation completed",
                {
                    "db_avg_ms": summary.db_avg_ms,
                    "redis_avg_ms": summary.redis_avg_ms,
                    "break_even_hit_rate": summary.break_even_hit_rate,
                    "cache_hit_rate": summary.cache_hit_rate,
                },
            )
            self._store.append_log(run_id, "INFO", "complete", "benchmark run completed")
        except Exception as exc:
            record.status = "failed"
            record.updated_at = utc_now_iso()
            record.finished_at = utc_now_iso()
            record.error_message = str(exc)
            self._store.write_run(record)
            self._store.append_log(run_id, "ERROR", "failed", str(exc))

    def _warmup(self, config: RunConfig) -> None:
        for index in range(min(3, config.iteration_count)):
            self._baseline_client.fetch_detail(str(index))

    def _run_baseline(self, run_id: str, config: RunConfig) -> list[float]:
        samples: list[float] = []
        for index in range(config.iteration_count):
            request_id = f"baseline-{index}"
            started = time.perf_counter()
            start_ms = elapsed_ms(started, started)
            self._store.append_event(run_id, FlowEvent(
                event_id=f"{request_id}-start",
                request_id=request_id,
                timestamp=start_ms,
                mode="db_only",
                event_type="request_started",
                stage="request",
                duration_ms=0,
                metadata={"record_id": str(index)},
            ))

            db_started = time.perf_counter()
            self._store.append_event(run_id, FlowEvent(
                event_id=f"{request_id}-db-start",
                request_id=request_id,
                timestamp=elapsed_ms(started, db_started),
                mode="db_only",
                event_type="db_query_started",
                stage="db_lookup",
                duration_ms=0,
                metadata={"record_id": str(index)},
            ))
            self._baseline_client.fetch_detail(str(index))
            db_finished = time.perf_counter()
            db_duration = elapsed_ms(db_started, db_finished)
            total_duration = elapsed_ms(started, db_finished)
            samples.append(total_duration)

            self._store.append_event(run_id, FlowEvent(
                event_id=f"{request_id}-db-finish",
                request_id=request_id,
                timestamp=elapsed_ms(started, db_finished),
                mode="db_only",
                event_type="db_query_completed",
                stage="db_lookup",
                duration_ms=db_duration,
                metadata={"record_id": str(index)},
            ))
            self._store.append_event(run_id, FlowEvent(
                event_id=f"{request_id}-response",
                request_id=request_id,
                timestamp=elapsed_ms(started, db_finished),
                mode="db_only",
                event_type="response_sent",
                stage="response",
                duration_ms=0,
                metadata={"total_duration_ms": total_duration},
            ))
        self._store.append_log(
            run_id,
            "INFO",
            "baseline_run",
            "baseline benchmark completed",
            {"sample_count": len(samples)},
        )
        return samples

    def _run_cache(self, run_id: str, config: RunConfig) -> tuple[list[float], int, int, int, int, int, dict[int, float]]:
        samples: list[float] = []
        cache_hits = 0
        cache_total = 0
        redis_miss_count = 0
        fallback_count = 0
        error_count = 0
        bucket_samples: dict[int, list[float]] = {}
        buckets = config.hit_rate_buckets or [50]

        for bucket in buckets:
            target_hit_count = max(0, min(config.iteration_count, round(config.iteration_count * bucket / 100)))
            for index in range(config.iteration_count):
                cache_total += 1
                record_id = f"{bucket}-{index}"
                key = f"benchmark:detail:{record_id}"
                request_id = f"cache-{bucket}-{index}"
                should_hit = index < target_hit_count
                if should_hit:
                    self._redis_client.set(key, f"cached:{record_id}")
                    self._redis_client.expire(key, config.ttl_seconds)
                else:
                    self._redis_client.delete(key)

                started = time.perf_counter()
                self._store.append_event(run_id, FlowEvent(
                    event_id=f"{request_id}-start",
                    request_id=request_id,
                    timestamp=0,
                    mode="cache_aside",
                    event_type="request_started",
                    stage="request",
                    duration_ms=0,
                    metadata={"record_id": record_id, "bucket": bucket},
                ))

                lookup_started = time.perf_counter()
                self._store.append_event(run_id, FlowEvent(
                    event_id=f"{request_id}-lookup-start",
                    request_id=request_id,
                    timestamp=elapsed_ms(started, lookup_started),
                    mode="cache_aside",
                    event_type="cache_lookup_started",
                    stage="redis_lookup",
                    duration_ms=0,
                    metadata={"key": key, "bucket": bucket},
                ))
                try:
                    cached_value = self._redis_client.get(key)
                    lookup_finished = time.perf_counter()
                    lookup_duration = elapsed_ms(lookup_started, lookup_finished)
                    self._store.append_event(run_id, FlowEvent(
                        event_id=f"{request_id}-lookup-finish",
                        request_id=request_id,
                        timestamp=elapsed_ms(started, lookup_finished),
                        mode="cache_aside",
                        event_type="cache_lookup_completed",
                        stage="redis_lookup",
                        duration_ms=lookup_duration,
                        metadata={"key": key, "bucket": bucket},
                    ))
                except MiniRedisError as exc:
                    error_count += 1
                    fallback_count += 1
                    lookup_finished = time.perf_counter()
                    lookup_duration = elapsed_ms(lookup_started, lookup_finished)
                    self._store.append_event(run_id, FlowEvent(
                        event_id=f"{request_id}-fallback",
                        request_id=request_id,
                        timestamp=elapsed_ms(started, lookup_finished),
                        mode="cache_aside",
                        event_type="fallback_used",
                        stage="redis_lookup",
                        duration_ms=lookup_duration,
                        metadata={"reason": str(exc), "key": key, "bucket": bucket},
                    ))
                    self._store.append_event(run_id, FlowEvent(
                        event_id=f"{request_id}-error",
                        request_id=request_id,
                        timestamp=elapsed_ms(started, lookup_finished),
                        mode="cache_aside",
                        event_type="error",
                        stage="redis_lookup",
                        duration_ms=0,
                        metadata={"message": str(exc)},
                    ))
                    db_started = time.perf_counter()
                    self._store.append_event(run_id, FlowEvent(
                        event_id=f"{request_id}-db-start",
                        request_id=request_id,
                        timestamp=elapsed_ms(started, db_started),
                        mode="cache_aside",
                        event_type="db_query_started",
                        stage="db_lookup",
                        duration_ms=0,
                        metadata={"record_id": record_id, "bucket": bucket},
                    ))
                    self._baseline_client.fetch_detail(record_id)
                    db_finished = time.perf_counter()
                    total_duration = elapsed_ms(started, db_finished)
                    samples.append(total_duration)
                    bucket_samples.setdefault(bucket, []).append(total_duration)
                    self._store.append_event(run_id, FlowEvent(
                        event_id=f"{request_id}-db-finish",
                        request_id=request_id,
                        timestamp=elapsed_ms(started, db_finished),
                        mode="cache_aside",
                        event_type="db_query_completed",
                        stage="db_lookup",
                        duration_ms=elapsed_ms(db_started, db_finished),
                        metadata={"record_id": record_id, "bucket": bucket},
                    ))
                    self._store.append_event(run_id, FlowEvent(
                        event_id=f"{request_id}-response",
                        request_id=request_id,
                        timestamp=elapsed_ms(started, db_finished),
                        mode="cache_aside",
                        event_type="response_sent",
                        stage="response",
                        duration_ms=0,
                        metadata={"total_duration_ms": total_duration, "cache_status": "fallback"},
                    ))
                    continue

                if cached_value is not None:
                    cache_hits += 1
                    finished = time.perf_counter()
                    total_duration = elapsed_ms(started, finished)
                    samples.append(total_duration)
                    bucket_samples.setdefault(bucket, []).append(total_duration)
                    self._store.append_event(run_id, FlowEvent(
                        event_id=f"{request_id}-hit",
                        request_id=request_id,
                        timestamp=elapsed_ms(started, lookup_finished),
                        mode="cache_aside",
                        event_type="cache_hit",
                        stage="redis_lookup",
                        duration_ms=lookup_duration,
                        metadata={"key": key, "bucket": bucket},
                    ))
                    self._store.append_event(run_id, FlowEvent(
                        event_id=f"{request_id}-response",
                        request_id=request_id,
                        timestamp=elapsed_ms(started, finished),
                        mode="cache_aside",
                        event_type="response_sent",
                        stage="response",
                        duration_ms=0,
                        metadata={"total_duration_ms": total_duration, "cache_status": "hit"},
                    ))
                    continue

                redis_miss_count += 1
                self._store.append_event(run_id, FlowEvent(
                    event_id=f"{request_id}-miss",
                    request_id=request_id,
                    timestamp=elapsed_ms(started, lookup_finished),
                    mode="cache_aside",
                    event_type="cache_miss",
                    stage="redis_lookup",
                    duration_ms=lookup_duration,
                    metadata={"key": key, "bucket": bucket},
                ))

                db_started = time.perf_counter()
                self._store.append_event(run_id, FlowEvent(
                    event_id=f"{request_id}-db-start",
                    request_id=request_id,
                    timestamp=elapsed_ms(started, db_started),
                    mode="cache_aside",
                    event_type="db_query_started",
                    stage="db_lookup",
                    duration_ms=0,
                    metadata={"record_id": record_id, "bucket": bucket},
                ))
                self._baseline_client.fetch_detail(record_id)
                db_finished = time.perf_counter()
                self._store.append_event(run_id, FlowEvent(
                    event_id=f"{request_id}-db-finish",
                    request_id=request_id,
                    timestamp=elapsed_ms(started, db_finished),
                    mode="cache_aside",
                    event_type="db_query_completed",
                    stage="db_lookup",
                    duration_ms=elapsed_ms(db_started, db_finished),
                    metadata={"record_id": record_id, "bucket": bucket},
                ))

                writeback_started = time.perf_counter()
                cache_status = "miss"
                try:
                    self._redis_client.set(key, f"cached:{record_id}")
                    self._redis_client.expire(key, config.ttl_seconds)
                    writeback_finished = time.perf_counter()
                    self._store.append_event(run_id, FlowEvent(
                        event_id=f"{request_id}-cache-set",
                        request_id=request_id,
                        timestamp=elapsed_ms(started, writeback_finished),
                        mode="cache_aside",
                        event_type="cache_set",
                        stage="writeback",
                        duration_ms=elapsed_ms(writeback_started, writeback_finished),
                        metadata={"key": key, "ttl_seconds": config.ttl_seconds},
                    ))
                except MiniRedisError as exc:
                    error_count += 1
                    fallback_count += 1
                    cache_status = "miss_writeback_failed"
                    writeback_finished = time.perf_counter()
                    self._store.append_event(run_id, FlowEvent(
                        event_id=f"{request_id}-writeback-fallback",
                        request_id=request_id,
                        timestamp=elapsed_ms(started, writeback_finished),
                        mode="cache_aside",
                        event_type="fallback_used",
                        stage="writeback",
                        duration_ms=elapsed_ms(writeback_started, writeback_finished),
                        metadata={"reason": str(exc), "key": key, "bucket": bucket},
                    ))
                    self._store.append_event(run_id, FlowEvent(
                        event_id=f"{request_id}-writeback-error",
                        request_id=request_id,
                        timestamp=elapsed_ms(started, writeback_finished),
                        mode="cache_aside",
                        event_type="error",
                        stage="writeback",
                        duration_ms=0,
                        metadata={"message": str(exc)},
                    ))

                finished = time.perf_counter()
                total_duration = elapsed_ms(started, finished)
                samples.append(total_duration)
                bucket_samples.setdefault(bucket, []).append(total_duration)
                self._store.append_event(run_id, FlowEvent(
                    event_id=f"{request_id}-response",
                    request_id=request_id,
                    timestamp=elapsed_ms(started, finished),
                    mode="cache_aside",
                    event_type="response_sent",
                    stage="response",
                    duration_ms=0,
                    metadata={"total_duration_ms": total_duration, "cache_status": cache_status},
                ))
        self._store.append_log(
            run_id,
            "INFO",
            "cache_run",
            "cache benchmark completed",
            {
                "sample_count": len(samples),
                "cache_hits": cache_hits,
                "cache_total": cache_total,
                "redis_miss_count": redis_miss_count,
                "fallback_count": fallback_count,
                "error_count": error_count,
            },
        )
        bucket_averages = {
            bucket: round(statistics.fmean(values), 2)
            for bucket, values in bucket_samples.items()
            if values
        }
        return samples, cache_hits, cache_total, redis_miss_count, fallback_count, error_count, bucket_averages

    def _run_reference(self, run_id: str, config: RunConfig) -> list[float]:
        samples: list[float] = []
        for index in range(config.iteration_count):
            record_id = f"reference-{index}"
            key = f"benchmark:detail:{record_id}"
            request_id = f"reference-{index}"
            self._redis_client.set(key, f"cached:{record_id}")
            self._redis_client.expire(key, config.ttl_seconds)
            started = time.perf_counter()
            self._store.append_event(run_id, FlowEvent(
                event_id=f"{request_id}-start",
                request_id=request_id,
                timestamp=0,
                mode="redis_only_reference",
                event_type="request_started",
                stage="request",
                duration_ms=0,
                metadata={"record_id": record_id},
            ))
            lookup_started = time.perf_counter()
            self._redis_client.get(key)
            lookup_finished = time.perf_counter()
            self._store.append_event(run_id, FlowEvent(
                event_id=f"{request_id}-hit",
                request_id=request_id,
                timestamp=elapsed_ms(started, lookup_finished),
                mode="redis_only_reference",
                event_type="cache_hit",
                stage="redis_lookup",
                duration_ms=elapsed_ms(lookup_started, lookup_finished),
                metadata={"key": key},
            ))
            finished = time.perf_counter()
            total_duration = elapsed_ms(started, finished)
            samples.append(total_duration)
            self._store.append_event(run_id, FlowEvent(
                event_id=f"{request_id}-response",
                request_id=request_id,
                timestamp=elapsed_ms(started, finished),
                mode="redis_only_reference",
                event_type="response_sent",
                stage="response",
                duration_ms=0,
                metadata={"total_duration_ms": total_duration, "cache_status": "reference_hit"},
            ))
        self._store.append_log(
            run_id,
            "INFO",
            "reference_run",
            "reference benchmark completed",
            {"sample_count": len(samples)},
        )
        return samples


def build_summary(
    baseline_samples: list[float],
    cache_samples: list[float],
    reference_samples: list[float],
    buckets: list[int],
    bucket_averages: dict[int, float],
    cache_hits: int,
    cache_total: int,
    db_only_count: int,
    redis_hit_count: int,
    redis_miss_count: int,
    fallback_count: int,
    error_count: int,
) -> RunSummary:
    db_avg_ms = statistics.fmean(baseline_samples) if baseline_samples else 0.0
    redis_avg_ms = statistics.fmean(cache_samples) if cache_samples else 0.0
    reference_avg_ms = statistics.fmean(reference_samples) if reference_samples else None
    p95_db_ms = percentile_95(baseline_samples)
    p95_redis_ms = percentile_95(cache_samples)
    p95_reference_ms = percentile_95(reference_samples) if reference_samples else None
    speedup_ratio = round(db_avg_ms / redis_avg_ms, 2) if redis_avg_ms else 0.0
    improvement_percent = round((1 - (redis_avg_ms / db_avg_ms)) * 100, 2) if db_avg_ms else 0.0
    cache_hit_rate = round((cache_hits / cache_total) * 100, 2) if cache_total else 0.0
    break_even_hit_rate = next(
        (
            bucket
            for bucket in sorted(buckets)
            if bucket in bucket_averages and bucket_averages[bucket] <= db_avg_ms
        ),
        None,
    )
    return RunSummary(
        db_avg_ms=round(db_avg_ms, 2),
        redis_avg_ms=round(redis_avg_ms, 2),
        reference_avg_ms=round(reference_avg_ms, 2) if reference_avg_ms is not None else None,
        p95_db_ms=round(p95_db_ms, 2),
        p95_redis_ms=round(p95_redis_ms, 2),
        p95_reference_ms=round(p95_reference_ms, 2) if p95_reference_ms is not None else None,
        speedup_ratio=speedup_ratio,
        improvement_percent=improvement_percent,
        break_even_hit_rate=break_even_hit_rate,
        cache_hit_rate=cache_hit_rate,
        db_only_count=db_only_count,
        redis_hit_count=redis_hit_count,
        redis_miss_count=redis_miss_count,
        fallback_count=fallback_count,
        error_count=error_count,
    )


def percentile_95(samples: list[float]) -> float:
    if not samples:
        return 0.0
    ordered = sorted(samples)
    index = max(0, int(len(ordered) * 0.95) - 1)
    return ordered[index]


def elapsed_ms(started: float, finished: float) -> float:
    return round((finished - started) * 1000, 2)


def read_git_head(path: Path) -> str | None:
    head_path = path / ".git" / "HEAD"
    if not head_path.exists():
        return None
    head = head_path.read_text().strip()
    if head.startswith("ref:"):
        ref_path = path / ".git" / head.split(" ", 1)[1]
        if ref_path.exists():
            return ref_path.read_text().strip()[:12]
    return head[:12]

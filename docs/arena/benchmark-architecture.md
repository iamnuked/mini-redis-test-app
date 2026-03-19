# Arena Benchmark Architecture

## 1. 목적

이 문서는 Arena를 "동작 시각화 도구"에서 "속도 비교가 가능한 비교 시스템"으로 재설계하기 위한 기준 문서다.

현재 구조는 gateway 내부에서 두 lane을 직접 실행하고, DB도 인메모리 딕셔너리로 대체하고 있다. 이 방식은 cache hit/miss, 처리 경로, TTL 동작을 보여주는 데는 유효하지만, `redis + db`와 `db only`의 처리 속도를 공정하게 비교하기에는 부적절하다.

이 문서의 목표는 다음 세 가지다.

1. lane 실행을 프로세스 단위로 분리한다.
2. lane별 DB 상태를 분리한다.
3. 속도 비교 기준을 gateway 왕복시간이 아니라 lane 내부 측정값으로 고정한다.

## 2. 목표 구조

```text
browser
  -> gateway :8000

gateway
  -> lane-a :8001
  -> lane-b :8002

lane-a
  -> mini-redis :6379
  -> mongo-a :27017

lane-b
  -> mongo-b :27018
```

### 2-1. 서비스 책임

- `gateway`
  - 브라우저와 HTTP/SSE 통신
  - `request_id` 발급
  - lane A/B fan-out
  - lane 결과 집계
  - scenario orchestration
  - benchmark summary 계산

- `lane-a`
  - `redis + mongo` 처리
  - Redis hit/miss 계산
  - Mongo read/write
  - lane 내부 timing 측정

- `lane-b`
  - `mongo only` 처리
  - Mongo read/write
  - lane 내부 timing 측정

- `mini-redis`
  - cache engine

- `mongo-a`, `mongo-b`
  - lane별 독립 저장소

### 2-2. 최소 타협안

로컬 개발 편의를 위해 Mongo 프로세스를 1개만 둘 수 있다. 이 경우에도 DB 이름은 반드시 분리한다.

- `arena_lane_a`
- `arena_lane_b`

이 타협안은 현재 구조보다 훨씬 낫지만, strict benchmark 구성보다는 덜 정확하다.

## 3. 프로토콜

- Browser <-> Gateway
  - HTTP + SSE
- Gateway <-> Lane A/B
  - HTTP JSON
- Lane A <-> mini-redis
  - Redis RESP/TCP
- Lane A/B <-> MongoDB
  - Mongo driver/TCP

중요:

- Redis 경로는 HTTP가 아니다.
- Browser는 Redis와 직접 통신하지 않는다.
- Gateway는 lane logic을 직접 실행하지 않는다.

## 4. 속도 비교 원칙

속도 비교 기준은 gateway에서 측정한 전체 왕복시간이 아니라, 각 lane 내부에서 측정한 `service_time_ms`다.

### 4-1. 측정 규칙

- Gateway는 lane A/B에 거의 동시에 요청만 보낸다.
- 각 lane은 자기 프로세스 내부에서 시작 시각과 종료 시각을 기록한다.
- 비교 기준은 lane 응답의 `service_time_ms`다.
- Gateway에서 관찰한 HTTP 왕복시간은 참고용 observability 값으로만 저장한다.
- 단건 latency보다 반복 실행 기반 percentile을 우선한다.

### 4-2. 필수 지표

- `service_time_ms`
- `mongo_reads`
- `cache.hit`
- `cache.miss`
- `redis_time_ms`
- `db_time_ms`
- `gateway_round_trip_ms`
- `p50`
- `p95`
- `p99`

## 5. 데이터 격리 원칙

lane A와 lane B는 같은 seed를 공유하되, 실행 상태는 분리되어야 한다.

원칙:

- 같은 logical dataset으로 시작한다.
- lane A와 lane B는 다른 DB namespace를 사용한다.
- reset 시 두 lane 모두 같은 초기 상태로 복원한다.
- lane A에서의 cache fill, TTL, delete가 lane B 상태에 영향을 주면 안 된다.

## 6. 공통 Lane API

### 6-1. `POST /execute`

요청:

```json
{
  "request_id": "req-1234",
  "mode": "manual",
  "command": "GET",
  "key": "user:1",
  "value": null,
  "ttl_enabled": true
}
```

응답:

```json
{
  "request_id": "req-1234",
  "lane": "redis_db",
  "status": "ok",
  "value_preview": "{\"name\":\"kim\"}",
  "path": ["redis_read", "redis_hit"],
  "storage_changes": ["Redis value returned", "Mongo unchanged"],
  "cache": {
    "hit": true,
    "miss": false
  },
  "mongo_reads": 0,
  "metrics": {
    "service_time_ms": 1.42,
    "db_time_ms": 0.31,
    "redis_time_ms": 0.72,
    "started_at_ns": 100000000,
    "finished_at_ns": 101420000
  }
}
```

### 6-2. 추가 endpoint

- `POST /reset`
- `POST /seed`
- `GET /health`

## 7. Gateway API

Gateway는 브라우저에 아래 endpoint를 유지한다.

- `POST /api/manual-command`
- `POST /api/scenarios/run`
- `POST /api/scenarios/reset`
- `GET /api/events`
- `GET /api/health`

Gateway 응답은 lane A/B 결과를 묶어서 내려준다.

```json
{
  "request": {
    "request_id": "req-1234",
    "mode": "manual",
    "command": "GET",
    "key": "user:1",
    "value": null,
    "ttl_enabled": true
  },
  "redis_db": { "...": "lane-a result" },
  "db_only": { "...": "lane-b result" },
  "summary": {
    "faster_lane": "redis_db",
    "latency_gap_ms": 2.18,
    "fewer_mongo_reads_lane": "redis_db",
    "mongo_read_gap": 1
  }
}
```

## 8. 시나리오 분류

속도 비교는 시나리오별로 분리해서 봐야 한다.

- `Read`
- `Write`
- `Mixed`
- `TTL churn`

해석 기준:

- `Read`는 hot-cold 분포와 memory profile에 따라 Redis 이점이 가장 잘 드러나는 구간이다.
- `Write`는 lane A가 lane B보다 느릴 수 있다.
- `Mixed`는 실제 앱과 가까운 절충 workload다.

## 9. 대시보드 구성

UI는 역할을 분리한다.

### 9-1. Trace View

- request path
- cache hit/miss
- storage changes
- lane별 개별 결과

### 9-2. Benchmark View

- `p50`, `p95`, `p99`
- hit rate
- mongo read 차이
- speedup ratio

## 10. 구현 순서

1. 공통 request/response 모델을 `internal/arena/common`으로 이동
2. `lane-a`, `lane-b` 전용 엔트리포인트와 API 추가
3. 기존 adapter 로직을 lane service로 이동
4. gateway에 lane HTTP client 추가
5. 실제 Mongo repository 추가
6. `reset/seed/health` endpoint 추가
7. benchmark 집계 로직 추가
8. dashboard에 benchmark view 추가
9. docker compose 추가
10. integration test 추가

## 11. 완료 기준

아래 조건을 만족하면 속도 비교 가능한 Arena로 본다.

- gateway가 lane A/B에 fan-out 가능
- lane별 DB 상태가 독립적임
- lane 내부 `service_time_ms`가 기록됨
- Redis lane과 DB-only lane이 실제 Mongo 기반으로 실행됨
- warm read에서 Redis 이점이 통계로 관찰됨
- UI에서 trace와 benchmark가 분리되어 보임

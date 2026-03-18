# mini-redis Benchmark API 명세서

## 1. 문서 목적

이 문서는 현재 `app/api/server.py` 구현을 기준으로 benchmark 컨트롤러 API를 명세한다.

중요:

- 이 문서는 "이상적인 설계"가 아니라 "지금 실제로 동작하는 API"를 기준으로 작성했다.
- 프론트엔드 구현, 수동 테스트, 후속 API 개선 작업의 기준 문서로 사용한다.

## 2. 기본 정보

- Base URL 예시: `http://127.0.0.1:8000`
- Content-Type: `application/json; charset=utf-8`
- 인증: 없음
- 동시 실행 제한: 활성 benchmark run은 한 번에 1개만 허용

비고:

- 실제 포트는 `BENCHMARK_CONTROLLER_PORT`로 바뀔 수 있다.
- 최근 수동 검증은 `8000` 고정이 아니라 `8001`, `8011` 같은 대체 포트에서도 수행했다.

프론트엔드 연결 기본값:

- 백엔드는 same-origin 기준으로 정적 프론트 파일을 함께 서빙할 수 있다.
- 기본 정적 경로 예:
  - `GET /`
  - `GET /app.js`
  - `GET /styles.css`
- 프론트 기본 API base는 `/api` 다.
- 교차 origin 개발 환경에서는 reverse proxy 또는 CORS 헤더가 필요하다.

환경 변수:

- `BENCHMARK_CONTROLLER_HOST`
- `BENCHMARK_CONTROLLER_PORT`
- `MINI_REDIS_HOST`
- `MINI_REDIS_PORT`
- `MINI_REDIS_TIMEOUT_SECONDS`

시간 표현 규칙:

- run 메타데이터의 시각 필드(`created_at`, `updated_at`, `started_at`, `finished_at`)는 UTC ISO-8601 문자열이다.
  - 예: `2026-03-18T12:34:56Z`
- `logs[].timestamp`는 Unix epoch seconds float 값이다.
  - 예: `1773832234.112`
- `events[].timestamp`는 "run 전체 기준 절대 시각"이 아니라 "개별 request 시작 시점 기준 경과 ms"다.
  - 예: `3.24`
- 1차 버전 replay와 흐름 UI의 기준 순서는 `events[]` 배열의 기록 순서다.

## 3. Run 상태 머신

`status`는 아래 값 중 하나를 가진다.

- `queued`
- `bootstrapping`
- `warming_up`
- `running_baseline`
- `running_cache`
- `running_reference`
- `aggregating`
- `completed`
- `failed`

## 4. 엔드포인트 요약

| Method | Path | 설명 |
| --- | --- | --- |
| `GET` | `/` | 프론트엔드 정적 진입 페이지 반환 |
| `GET` | `/api/health` | mini-redis 연결 상태 확인 |
| `GET` | `/api/benchmark-runs` | 최근 run 목록 조회 |
| `POST` | `/api/benchmark-runs` | 새 benchmark run 생성 |
| `GET` | `/api/benchmark-runs/{run_id}` | run 상태, 설정, summary, logs 조회 |
| `GET` | `/api/benchmark-runs/{run_id}/events` | run 이벤트 목록 조회 |
| `GET` | `/api/benchmark-runs/{run_id}/requests` | request 단위 timeline 뷰 조회 |
| `GET` | `/api/benchmark-runs/{run_id}/presentation` | 발표 화면용 집계 read model 조회 |
| `OPTIONS` | `/api/*` | 기본 preflight/CORS 응답 |

## 5. 상세 명세

### 5-0. 정적 진입점 및 공통 헤더

#### `GET /`

프론트엔드 진입용 `index.html`을 반환한다.

현재 구현 메모:

- same-origin 대시보드 접근의 기본 진입점이다.
- 정적 파일은 `app/ui/static` 기준으로 제공된다.

#### `OPTIONS /api/*`

기본 preflight 응답을 반환한다.

현재 응답 헤더:

- `Access-Control-Allow-Origin: *`
- `Access-Control-Allow-Methods: GET, POST, OPTIONS`
- `Access-Control-Allow-Headers: Content-Type`

주의:

- 이 설정은 로컬 개발과 연결 확인을 위한 기본값이다.
- 운영 환경의 세밀한 origin 제어 정책을 의미하지는 않는다.

### 5-1. `GET /api/health`

mini-redis 서버와 `HELLO 3` 기반 health check를 수행한다.

#### 200 OK

mini-redis 연결은 되었고, 응답은 받았을 때 반환한다.

```json
{
  "status": "ok",
  "host": "127.0.0.1",
  "port": 6379
}
```

또는 응답은 받았지만 mini-redis 판별이 실패한 경우 아래처럼 올 수 있다.

```json
{
  "status": "down",
  "host": "127.0.0.1",
  "port": 6379
}
```

#### 503 Service Unavailable

소켓 연결 실패, 타임아웃, RESP 에러 등 `MiniRedisError`가 발생하면 반환한다.

```json
{
  "status": "down",
  "host": "127.0.0.1",
  "port": 6379,
  "error": "[Errno 61] Connection refused"
}
```

### 5-2. `GET /api/benchmark-runs`

저장된 run 목록을 최신순으로 반환한다.

#### 200 OK

```json
{
  "runs": [
    {
      "run_id": "run_1773832200123",
      "status": "completed",
      "scenario": "detail_page",
      "created_at": "2026-03-18T12:30:00Z",
      "updated_at": "2026-03-18T12:30:04Z"
    }
  ]
}
```

응답 필드:

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `run_id` | `string` | run 식별자 |
| `status` | `string` | run 상태 |
| `scenario` | `string` | run 생성 시 전달된 시나리오 |
| `created_at` | `string` | 생성 시각, UTC ISO-8601 |
| `updated_at` | `string` | 마지막 갱신 시각, UTC ISO-8601 |

### 5-3. `POST /api/benchmark-runs`

새 benchmark run을 생성하고 비동기 실행을 시작한다.

run 생성 직후 상태는 항상 `queued`다.

#### Request Body

모든 필드는 선택이다. 생략 시 기본값이 적용된다.

```json
{
  "scenario": "detail_page",
  "iteration_count": 10,
  "concurrency": 1,
  "hit_rate_buckets": [0, 50, 100],
  "ttl_seconds": 30,
  "include_reference": false
}
```

| 필드 | 타입 | 기본값 | 설명 |
| --- | --- | --- | --- |
| `scenario` | `string` | `"detail_page"` | benchmark 시나리오 이름 |
| `iteration_count` | `integer` | `10` | mode별 반복 횟수 |
| `concurrency` | `integer` | `1` | 저장은 되지만 현재 runner에서 실제 병렬 실행 제어에는 사용되지 않음 |
| `hit_rate_buckets` | `integer[]` | `[0, 50, 100]` | cache run에서 사용할 적중률 버킷 목록 |
| `ttl_seconds` | `integer` | `30` | cache key TTL 초 단위 |
| `include_reference` | `boolean` | `false` | `Redis Only` 참고 run 포함 여부 |

#### Validation Rules

- `iteration_count > 0`
- `concurrency > 0`
- `ttl_seconds > 0`
- `hit_rate_buckets`는 비어 있으면 안 됨
- `hit_rate_buckets`의 각 값은 `0 <= bucket <= 100`

#### 201 Created

```json
{
  "run_id": "run_1773832200123",
  "status": "queued",
  "scenario": "detail_page",
  "created_at": "2026-03-18T12:30:00Z"
}
```

#### 400 Bad Request

유효성 검증 실패 시 반환한다.

```json
{
  "error": "ttl_seconds must be greater than 0"
}
```

가능한 에러 메시지 예:

- `iteration_count must be greater than 0`
- `concurrency must be greater than 0`
- `ttl_seconds must be greater than 0`
- `hit_rate_buckets must not be empty`
- `hit_rate_buckets must be between 0 and 100`
- `invalid JSON body`
- `JSON body must be an object`

#### 409 Conflict

진행 중인 run이 이미 있으면 반환한다.

```json
{
  "error": "another benchmark run is already active"
}
```

### 5-4. `GET /api/benchmark-runs/{run_id}`

특정 run의 현재 상태와 상세 정보를 조회한다.

#### 200 OK

```json
{
  "run_id": "run_1773832200123",
  "status": "completed",
  "config": {
    "scenario": "detail_page",
    "iteration_count": 10,
    "concurrency": 1,
    "hit_rate_buckets": [0, 50, 100],
    "ttl_seconds": 30,
    "include_reference": true
  },
  "created_at": "2026-03-18T12:30:00Z",
  "updated_at": "2026-03-18T12:30:04Z",
  "started_at": "2026-03-18T12:30:00Z",
  "finished_at": "2026-03-18T12:30:04Z",
  "summary": {
    "db_avg_ms": 182.4,
    "redis_avg_ms": 24.1,
    "reference_avg_ms": 9.8,
    "p95_db_ms": 231.2,
    "p95_redis_ms": 31.4,
    "p95_reference_ms": 12.0,
    "speedup_ratio": 7.57,
    "improvement_percent": 86.79,
    "break_even_hit_rate": 50,
    "cache_hit_rate": 62.0,
    "db_only_count": 10,
    "redis_hit_count": 18,
    "redis_miss_count": 12,
    "fallback_count": 0,
    "error_count": 0
  },
  "error_message": null,
  "mini_redis_commit": "abc123def456",
  "app_commit": "fed654cba321",
  "logs": [
    {
      "timestamp": 1773832200.12,
      "level": "INFO",
      "stage": "bootstrap",
      "message": "benchmark queued",
      "metadata": {}
    }
  ]
}
```

#### 응답 필드

상위 필드:

| 필드 | 타입 | nullable | 설명 |
| --- | --- | --- | --- |
| `run_id` | `string` | 아니오 | run 식별자 |
| `status` | `string` | 아니오 | run 상태 |
| `config` | `object` | 아니오 | 실행 설정 |
| `created_at` | `string` | 아니오 | 생성 시각 |
| `updated_at` | `string` | 아니오 | 마지막 갱신 시각 |
| `started_at` | `string` | 예 | 실행 시작 시각 |
| `finished_at` | `string` | 예 | 실행 종료 시각 |
| `summary` | `object` | 예 | 완료 시 summary |
| `error_message` | `string` | 예 | 실패 시 에러 메시지 |
| `mini_redis_commit` | `string` | 예 | `.tmp/mini-redis-dev` git HEAD 축약 해시 |
| `app_commit` | `string` | 예 | 현재 앱 git HEAD 축약 해시 |
| `logs` | `object[]` | 아니오 | run 로그 목록 |

`summary` 필드:

| 필드 | 타입 | nullable | 설명 |
| --- | --- | --- | --- |
| `db_avg_ms` | `number` | 아니오 | DB Only 평균 지연시간 |
| `redis_avg_ms` | `number` | 아니오 | Redis + DB 평균 지연시간 |
| `reference_avg_ms` | `number` | 예 | Redis Only reference 평균 지연시간 |
| `p95_db_ms` | `number` | 아니오 | DB Only p95 |
| `p95_redis_ms` | `number` | 아니오 | Redis + DB p95 |
| `p95_reference_ms` | `number` | 예 | Redis Only reference p95 |
| `speedup_ratio` | `number` | 아니오 | `db_avg_ms / redis_avg_ms` |
| `improvement_percent` | `number` | 아니오 | 평균 지연시간 개선율 |
| `break_even_hit_rate` | `integer` | 예 | bucket별 `Redis + DB` 평균이 `DB Only` 평균 이하가 되는 첫 bucket |
| `cache_hit_rate` | `number` | 아니오 | 전체 cache 요청 기준 적중률 |
| `db_only_count` | `integer` | 아니오 | baseline request 수 |
| `redis_hit_count` | `integer` | 아니오 | cache hit 수 |
| `redis_miss_count` | `integer` | 아니오 | cache miss 수 |
| `fallback_count` | `integer` | 아니오 | fallback 발생 수 |
| `error_count` | `integer` | 아니오 | cache run 중 error 이벤트 수 |

`logs[]` 필드:

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `timestamp` | `number` | Unix epoch seconds |
| `level` | `string` | 예: `INFO`, `ERROR` |
| `stage` | `string` | 예: `bootstrap`, `baseline_run`, `failed` |
| `message` | `string` | 로그 메시지 |
| `metadata` | `object` | 로그 부가 정보. 값이 없으면 빈 객체 |

응답 정규화 규칙:

- `logs[].metadata`는 값이 없더라도 항상 객체로 내려간다.

#### 404 Not Found

```json
{
  "error": "run not found"
}
```

### 5-5. `GET /api/benchmark-runs/{run_id}/events`

특정 run의 flow event 목록을 조회한다.

#### Query Parameters

| 이름 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `after` | `number` | 아니오 | `event.timestamp` 초과 값만 필터링 |

요청 예:

- `/api/benchmark-runs/run_1773832200123/events`
- `/api/benchmark-runs/run_1773832200123/events?after=3.5`

#### 200 OK

```json
{
  "run_id": "run_1773832200123",
  "events": [
    {
      "event_id": "cache-50-1-start",
      "request_id": "cache-50-1",
      "timestamp": 0,
      "mode": "cache_aside",
      "event_type": "request_started",
      "stage": "request",
      "duration_ms": 0,
      "metadata": {
        "record_id": "50-1",
        "bucket": 50
      }
    },
    {
      "event_id": "cache-50-1-hit",
      "request_id": "cache-50-1",
      "timestamp": 2.31,
      "mode": "cache_aside",
      "event_type": "cache_hit",
      "stage": "redis_lookup",
      "duration_ms": 2.31,
      "metadata": {
        "key": "benchmark:detail:50-1",
        "bucket": 50
      }
    }
  ]
}
```

`events[]` 필드:

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `event_id` | `string` | 이벤트 식별자 |
| `request_id` | `string` | request 식별자 |
| `timestamp` | `number` | request 시작 이후 경과 ms |
| `mode` | `string` | `db_only`, `cache_aside`, `redis_only_reference` |
| `event_type` | `string` | 이벤트 종류 |
| `stage` | `string` | 처리 단계 |
| `duration_ms` | `number` | 해당 단계 소요 시간 |
| `metadata` | `object` | 이벤트 부가 정보 |

응답 정규화 규칙:

- `events[].timestamp`와 `events[].duration_ms`는 숫자형으로 내려간다.
- `events[].metadata`는 값이 없더라도 항상 객체로 내려간다.

#### 400 Bad Request

`after`가 숫자로 파싱되지 않으면 반환한다.

```json
{
  "error": "invalid after query parameter"
}
```

중요한 주의점:

- `after`는 절대 시각 커서가 아니다.
- 현재 구현은 `event.timestamp`를 request 상대 시간으로 기록한다.
- 따라서 `after`는 "증분 스트리밍 커서"로 쓰기에는 부정확하다.
- 프론트엔드는 현재 메인 화면의 1차 데이터 소스로 `events[]`를 쓰지 않는다.
- raw `events[]`는 디버깅, 원본 검증, 후속 실시간 확장용 보조 데이터로 유지한다.
- event 기반 추가 화면이 필요하면 전체 이벤트 재조회 후 `event_id` 기준 dedupe 하는 방식이 더 안전하다.
- replay와 lane playback은 `events[]` 배열 순서를 기본 chronology로 사용한다.
- 현재 구현은 `GET /api/benchmark-runs/{run_id}/events` 호출 시 run 존재 여부를 별도로 검증하지 않는다.
- 즉, 존재하지 않는 `run_id` 또는 아직 이벤트 파일이 없는 run도 `200 OK`와 빈 배열을 반환할 수 있다.

### 5-6. `GET /api/benchmark-runs/{run_id}/requests`

특정 run의 event stream을 request 단위 timeline 뷰로 재구성해 반환한다.

현재 프론트 사용 방식:

- 흐름 레인 보드의 주 데이터 소스
- request detail 패널의 주 데이터 소스
- replay 대상 request 목록의 주 데이터 소스

#### 200 OK

```json
{
  "run_id": "run_1773832200123",
  "requests": [
    {
      "request_id": "cache-50-1",
      "mode": "cache_aside",
      "started_at_ms": 0.0,
      "finished_at_ms": 21.2,
      "total_duration_ms": 21.2,
      "cache_status": "miss",
      "path_summary": "App -> Redis -> DB -> Redis -> Response",
      "has_error": false,
      "stage_durations": {
        "request": 0.0,
        "redis_lookup": 2.31,
        "db_lookup": 16.29,
        "writeback": 2.6,
        "response": 0.0
      },
      "event_count": 4,
      "events": []
    }
  ]
}
```

`requests[]` 필드:

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `request_id` | `string` | request 식별자 |
| `mode` | `string` | `db_only`, `cache_aside`, `redis_only_reference` |
| `started_at_ms` | `number` | request 시작 상대 시각 |
| `finished_at_ms` | `number` | request 종료 상대 시각 |
| `total_duration_ms` | `number` | 응답 기준 총 소요 시간 |
| `cache_status` | `string` | `db_only`, `hit`, `miss`, `fallback`, `reference_hit` 등 |
| `path_summary` | `string` | 프론트 설명용 경로 요약 |
| `has_error` | `boolean` | 오류 포함 여부 |
| `stage_durations` | `object` | stage별 누적 duration |
| `event_count` | `integer` | 해당 request에 속한 event 수 |
| `events` | `object[]` | 정규화된 원본 event 배열 |

중요한 주의점:

- 현재 구현은 `GET /api/benchmark-runs/{run_id}/requests` 호출 시 run 존재 여부를 별도로 검증하지 않는다.
- 즉, 존재하지 않는 `run_id` 또는 아직 이벤트 파일이 없는 run도 `200 OK`와 빈 `requests` 배열을 반환할 수 있다.

### 5-7. `GET /api/benchmark-runs/{run_id}/presentation`

특정 run을 발표 화면에 바로 렌더링하기 위한 집계 read model을 반환한다.

현재 프론트 사용 방식:

- KPI 카드의 주 데이터 소스
- lane summary 카드의 주 데이터 소스
- latency/path/stage 보조 차트의 주 데이터 소스

비고:

- 발표용 첫 화면은 `chart_series.latency_comparison`를 가장 먼저 사용하고, 이 시리즈는 기본적으로 `DB Only`, `Redis Hit`, `Redis Miss`를 우선 노출한다.

#### 200 OK

```json
{
  "run_id": "run_1773832200123",
  "status": "completed",
  "scenario": "detail_page",
  "config": {
    "iteration_count": 10,
    "concurrency": 1,
    "ttl_seconds": 30
  },
  "kpis": {
    "db_avg_ms": 182.4,
    "redis_avg_ms": 24.1,
    "redis_hit_avg_ms": 12.7,
    "redis_miss_avg_ms": 41.5,
    "reference_avg_ms": 9.8,
    "speedup_ratio": 7.57,
    "improvement_percent": 86.79,
    "break_even_hit_rate": 50,
    "cache_hit_rate": 62.0,
    "error_count": 0
  },
  "lane_summary": [
    {
      "mode": "db_only",
      "label": "DB Only",
      "request_count": 10,
      "avg_duration_ms": 182.4,
      "hit_count": 0,
      "miss_count": 0,
      "fallback_count": 0,
      "error_count": 0
    }
  ],
  "chart_series": {
    "latency_comparison": [
      {
        "label": "DB Only Avg",
        "value": 182.4
      },
      {
        "label": "Redis Hit Avg",
        "value": 12.7
      },
      {
        "label": "Redis Miss Avg",
        "value": 41.5
      }
    ],
    "path_ratio": [
      {
        "label": "Redis Hit",
        "value": 18
      },
      {
        "label": "Redis Miss",
        "value": 12
      }
    ],
    "timeline_stage_totals": [
      {
        "label": "db_lookup",
        "value": 210.4
      }
    ]
  }
}
```

상위 필드:

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `run_id` | `string` | run 식별자 |
| `status` | `string` | run 상태 |
| `scenario` | `string` | 시나리오 이름 |
| `config` | `object` | 실행 설정 |
| `kpis` | `object \| null` | KPI 카드용 요약 |
| `lane_summary` | `object[]` | lane 카드용 모드 요약 |
| `chart_series` | `object` | 차트 렌더링용 시리즈 묶음 |

`kpis` 필드:

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `db_avg_ms` | `number` | DB Only 평균 |
| `redis_avg_ms` | `number` | Redis + DB 평균 |
| `redis_hit_avg_ms` | `number \| null` | Redis만 조회하고 끝난 적중 경로 평균 |
| `redis_miss_avg_ms` | `number \| null` | Redis 미스 후 DB까지 간 경로 평균 |
| `reference_avg_ms` | `number \| null` | Redis Only 평균 |
| `speedup_ratio` | `number` | 평균 기준 속도 향상 배수 |
| `improvement_percent` | `number` | 평균 기준 개선율 |
| `break_even_hit_rate` | `integer \| null` | 성능 역전 기준 적중률 |
| `cache_hit_rate` | `number` | 전체 적중률 |
| `error_count` | `integer` | 오류 수 |

`lane_summary[]` 필드:

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `mode` | `string` | lane 모드 |
| `label` | `string` | 표시 라벨 |
| `request_count` | `integer` | request 수 |
| `avg_duration_ms` | `number \| null` | lane 평균 duration |
| `hit_count` | `integer` | hit 수 |
| `miss_count` | `integer` | miss 수 |
| `fallback_count` | `integer` | fallback 수 |
| `error_count` | `integer` | error 수 |

`chart_series` 필드:

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `latency_comparison` | `object[]` | 기본적으로 `DB Only`, `Redis Hit`, `Redis Miss`를 우선 비교하는 평균 latency 시리즈 |
| `path_ratio` | `object[]` | 요청 경로 비율 시리즈 |
| `timeline_stage_totals` | `object[]` | stage별 누적 duration 시리즈 |

#### 404 Not Found

```json
{
  "error": "run not found"
}
```

## 6. Enum 참고

### 6-1. `mode`

- `db_only`
- `cache_aside`
- `redis_only_reference`

### 6-2. `event_type`

현재 구현에서 실제로 기록되는 값:

- `request_started`
- `db_query_started`
- `db_query_completed`
- `cache_lookup_started`
- `cache_lookup_completed`
- `cache_hit`
- `cache_miss`
- `cache_set`
- `fallback_used`
- `error`
- `response_sent`

TTL 만료를 적극 시뮬레이션하는 시나리오에서 선택적으로 추가할 수 있는 값:

- `ttl_expired`

### 6-3. `stage`

- `request`
- `redis_lookup`
- `db_lookup`
- `writeback`
- `response`

## 7. 구현 메모와 제한 사항

- `scenario`는 문자열로 자유롭게 받을 수 있지만, 현재 benchmark 로직은 사실상 `detail_page` 단일 시나리오 가정에 가깝다.
- `concurrency`는 API와 저장 모델에는 포함되지만, 현재 runner의 실제 실행 흐름에는 반영되지 않는다.
- 1차 대표 시나리오는 별도 전역 seed 단계를 두지 않고 cache run 내부 key priming/eviction으로 hit/miss를 만든다.
- `POST /api/benchmark-runs`는 run 생성 후 별도 worker thread로 즉시 실행을 시작한다.
- `GET /api/benchmark-runs/{run_id}`는 logs를 포함하지만 events는 포함하지 않는다.
- `GET /api/benchmark-runs/{run_id}/events`는 현재 unknown run에 대해서도 `404` 대신 빈 `events` 배열을 반환할 수 있다.
- 중지 API, 삭제 API, replay API는 아직 없다.
- 실시간 push 방식(SSE/WebSocket) 없이 polling 기반 조회만 지원한다.

## 8. 프론트엔드 연동 권장 흐름

1. 앱 시작 시 `GET /api/health`로 mini-redis 상태를 확인한다.
2. 최근 run 목록이 필요하면 `GET /api/benchmark-runs`를 호출한다.
3. 새 실행은 `POST /api/benchmark-runs`로 시작한다.
4. run 진행 중에는 `GET /api/benchmark-runs/{run_id}`를 주기적으로 polling한다.
5. 이벤트는 `GET /api/benchmark-runs/{run_id}/events`를 조회하되, 현재 구현에서는 전체 조회 + `event_id` dedupe를 권장한다.
6. request 상세 패널, 흐름 보드, replay 대상 request 목록은 `GET /api/benchmark-runs/{run_id}/requests`를 우선 사용한다.
7. KPI 카드, lane summary, 차트는 `GET /api/benchmark-runs/{run_id}/presentation`을 우선 사용한다.
8. `status`가 `completed` 또는 `failed`가 되면 polling을 멈춘다.

샘플 산출물:

- run 상세 예시: `docs/samples/sample-run-completed.json`
- event stream 예시: `docs/samples/sample-run-events.json`
- request timeline 예시: `docs/samples/sample-run-requests.json`
- presentation 예시: `docs/samples/sample-run-presentation.json`

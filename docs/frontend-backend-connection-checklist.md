# 프론트엔드-백엔드 연결 체크리스트

## 1. 목적

이 문서는 현재 벤치마크 UI 프론트엔드와 로컬 benchmark API 백엔드가 실제로 연결 가능한지 점검하기 위한 체크리스트다.

핵심은 아래 두 가지를 분리해서 확인하는 것이다.

- API 서버 자체가 정상 응답하는지
- 프론트엔드가 같은 origin 또는 적절한 프록시/CORS 설정으로 그 API를 실제로 호출할 수 있는지

## 2. 사전 조건

- `mini-redis` 서버가 실행 중이어야 한다.
- benchmark API 서버가 실행 중이어야 한다.
- 프론트엔드는 `app/ui/static` 기준 정적 파일을 제공하거나, 같은 내용을 포함한 개발 서버에서 실행 중이어야 한다.

빠른 시작 권장 순서:

1. `./scripts/stop_demo_stack.sh`
2. `./scripts/run_demo_stack.sh`
3. `./scripts/check_demo_stack.sh`

이 흐름을 먼저 사용하면 오래된 프로세스 때문에 다른 서버에 붙는 상황을 줄일 수 있다.

현재 백엔드는 `GET /` 에서 `app/ui/static/index.html` 을 same-origin으로 서빙할 수 있다.
기본 정적 파일 경로 예시:

- `/`
- `/app.js`
- `/styles.css`

이 항목은 현재 코드 기준으로 충족된다.

## 3. 런타임 구성 확인

### 3-1. API Base

프론트엔드는 아래 우선순위로 API base를 결정한다.

1. URL query parameter `?apiBase=...`
2. `localStorage["mini-redis-benchmark.api-base"]`
3. `<meta name="benchmark-api-base" content="/api">`

로컬 프리뷰 환경에서 위 기본값이 응답하지 않으면, 현재 프론트는 보조 후보로 `8000 -> 8001 -> 8002` 포트의 benchmark API를 순차 시도한다.

확인 항목:

- 현재 프론트가 어느 API base를 바라보는지 UI의 `API 기준 경로` 카드에서 확인한다.
- cross-origin이면 CORS 또는 reverse proxy가 준비되어 있는지 확인한다.

### 3-2. 기본 환경 변수

백엔드는 아래 환경 변수로 제어할 수 있다.

- `BENCHMARK_CONTROLLER_HOST`
- `BENCHMARK_CONTROLLER_PORT`
- `MINI_REDIS_HOST`
- `MINI_REDIS_PORT`
- `MINI_REDIS_TIMEOUT_SECONDS`

## 4. API 연결 체크

### 4-1. Health Check

- `GET /api/health`
- 기대 결과:
  - `200 OK` + `"status": "ok"` 또는
  - `503` + 명확한 에러 메시지

### 4-2. Run List

- `GET /api/benchmark-runs`
- 기대 결과:
  - `200 OK`
  - `runs` 배열 반환

### 4-3. Run Create

- `POST /api/benchmark-runs`
- 최소 payload 예시:

```json
{
  "scenario": "detail_page",
  "iteration_count": 2,
  "concurrency": 1,
  "ttl_seconds": 5,
  "hit_rate_buckets": [0, 100],
  "include_reference": true
}
```

- 기대 결과:
  - `201 Created`
  - `run_id` 반환

### 4-4. Run Status Polling

- `GET /api/benchmark-runs/{run_id}`
- 기대 결과:
  - 상태가 `queued -> bootstrapping -> ... -> completed/failed` 로 전이
  - `logs` 포함

### 4-5. Event Stream

- `GET /api/benchmark-runs/{run_id}/events`
- 기대 결과:
  - `events[]` 반환
  - 각 event는 `event_id`, `request_id`, `timestamp`, `mode`, `event_type`, `stage`, `duration_ms`, `metadata` 포함

주의:

- `after`는 절대 시각 커서가 아니다.
- 현재는 전체 재조회 + `event_id` dedupe가 안전하다.

### 4-6. Request Timeline Read Model

- `GET /api/benchmark-runs/{run_id}/requests`
- 기대 결과:
  - `requests[]` 반환
  - 각 request는 `path_summary`, `cache_status`, `stage_durations`, `total_duration_ms` 포함

### 4-7. Presentation Read Model

- `GET /api/benchmark-runs/{run_id}/presentation`
- 기대 결과:
  - `kpis`
  - `lane_summary`
  - `chart_series`

## 5. 프론트엔드 연결 체크

### 5-1. 같은 origin 여부

가장 쉬운 연결 조건:

- 프론트 페이지 origin = 백엔드 API origin
- 프론트는 `/api/...` 를 same-origin으로 호출

현재 로컬 백엔드는 이 same-origin 구성을 지원한다.

이 조건이 아니면:

- reverse proxy 또는
- CORS 허용

중 하나가 필요하다.

현재 백엔드는 기본 `OPTIONS` 응답과 `Access-Control-Allow-Origin: *` 헤더를 제공한다.
다만 운영 환경에서는 더 좁은 origin 제어가 필요할 수 있다.

### 5-2. 프론트 데이터 소스 체크

현재 권장 연결 방식:

- run 상태/로그: `GET /api/benchmark-runs/{run_id}`
- request detail/lane 설명: `GET /api/benchmark-runs/{run_id}/requests`
- KPI/차트/lane summary: `GET /api/benchmark-runs/{run_id}/presentation`

현재 프론트 구현도 위 흐름을 사용한다.
즉, `/events`는 더 이상 메인 화면의 1차 데이터 소스라기보다 request timeline에서 파생된 이벤트를 보조적으로 다루는 수준으로 보는 편이 맞다.

### 5-3. Replay 기준 체크

- 현재 프론트 replay는 `GET /api/benchmark-runs/{run_id}/requests` 로 받은 request timeline 순서를 기준으로 동작한다.
- 재생 타이머는 절대 시각 스트리밍이나 event timestamp 기반이 아니라, 사용자가 고른 재생 속도에 따른 고정 간격 step 방식이다.
- request 상대 duration과 stage 데이터는 상세 패널과 요약 표시에 사용한다.
- 따라서 절대 시각 스트리밍처럼 가정하면 안 되고, event-정밀 재생이 필요하면 후속 기능으로 따로 정의해야 한다.

## 6. 실패 시 체크 포인트

- `mini-redis` 미기동
- benchmark API 미기동
- API base 오설정
- cross-origin인데 CORS/프록시 없음
- `include_reference=false`인데 reference lane을 기대함
- `summary` 없는 실행 중 상태를 completed처럼 가정함

## 7. 현재 권장 판단 기준

- API 서버 응답이 정상이어도, 프론트가 다른 origin에서 열리고 CORS/프록시가 없으면 “실제 연결 완료”로 보면 안 된다.
- 현재 프론트가 `GET /api/benchmark-runs/{run_id}/requests` 와 `GET /api/benchmark-runs/{run_id}/presentation` 을 사용하고 있으므로, 설계 의도와의 주 데이터 소스 정합성은 맞는 상태다.

## 8. 현재 코드 기준 점검 결과

2026-03-18 기준, 현재 워크스페이스 코드와 프론트 구현을 대조한 결과는 아래와 같다.

- `[x]` 백엔드는 same-origin 정적 서빙 경로 `/`, `/app.js`, `/styles.css` 를 지원한다.
- `[x]` 백엔드는 `OPTIONS` 와 `Access-Control-Allow-Origin: *` 를 포함한 기본 CORS 헤더를 제공한다.
- `[x]` 프론트는 `?apiBase=...` -> `localStorage["mini-redis-benchmark.api-base"]` -> `<meta name="benchmark-api-base">` 순서로 API base를 결정한다.
- `[x]` 프론트는 run 상세와 로그는 `GET /api/benchmark-runs/{run_id}`, request detail과 흐름 보드는 `GET /api/benchmark-runs/{run_id}/requests`, KPI/차트/lane summary는 `GET /api/benchmark-runs/{run_id}/presentation` 을 우선 사용한다.
- `[x]` 프론트에는 run 전환 시 늦게 도착한 응답이 화면을 덮어쓰지 않도록 stale response guard가 있다.
- `[x]` 최신 코드 서버 기준 `GET /`, `GET /app.js`, `GET /api/health`, `GET /api/benchmark-runs`, `OPTIONS /api/benchmark-runs`, `POST /api/benchmark-runs`, `GET /api/benchmark-runs/{run_id}`, `GET /api/benchmark-runs/{run_id}/requests`, `GET /api/benchmark-runs/{run_id}/presentation` 실응답을 확인했다.

따라서 현재 문서 기준으로는 “구현 정합성은 맞고, 최신 서버 프로세스를 기준으로 same-origin 정적 서빙과 핵심 API 연결도 확인됨” 상태로 보는 게 가장 정확하다.

주의:

- 기존 `8000` 포트에 오래 떠 있던 예전 서버 프로세스가 있으면, 최신 코드 반영 상태와 다를 수 있다.
- 2026-03-18 재검증 시 실제 `127.0.0.1:8000` 프로세스는 `GET /` 에서 `404`, `OPTIONS /api/benchmark-runs` 에서 `501` 을 반환했다.
- 이후 최신 코드 서버를 `127.0.0.1:8011` 에서 재검증했을 때 same-origin 정적 서빙, CORS, run 생성, completed run, request/presentation read model 응답까지 모두 정상 동작했다.
- 실제 데모 전에는 백엔드 프로세스를 재시작해서 최신 코드 기준으로 다시 붙는 것이 안전하다.

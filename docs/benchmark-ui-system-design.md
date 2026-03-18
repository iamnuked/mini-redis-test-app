# mini-redis 벤치마크 UI 및 시스템 설계 문서

## 1. 문서 목적

이 문서는 팀이 만든 `mini-redis`를 청중에게 직관적으로 설명하고 시연하기 위한 벤치마크 UI 및 실행 시스템의 목표, 구조, 책임 경계, 데이터 흐름을 정의한다.

기준 대상은 현재 작업폴더의 `.tmp/mini-redis-dev`에 있는 `mini-redis` `dev` 브랜치다.

## 2. 문제 정의

현재 보여주고 싶은 핵심은 "캐시를 붙였을 때 앱 시나리오가 얼마나 빨라지고, 어떤 조건에서 이점이 생기는지"다.

하지만 단순 수치 몇 개만 제시하면 아래 문제가 생긴다.

- 청중이 어떤 상황에서 빨라졌는지 이해하기 어렵다.
- `mini-redis`의 현재 제약과 장점을 같이 설명하기 어렵다.
- 발표 때마다 실행 조건이 달라지면 결과 신뢰도가 떨어진다.

따라서 이 시스템은 단순 측정기가 아니라, `mini-redis`를 사용한 앱 경로와 사용하지 않은 앱 경로를 같은 조건에서 비교하고 그 과정을 시각적으로 보여주는 데모 시스템이어야 한다.

핵심 비교축은 `DB Only`와 `Redis + DB`다. `Redis Only`는 청중에게 "순수 캐시 접근의 참고 성능"을 보여주기 위한 보조 모드로만 다룬다.

## 3. 설계 목표

- `DB 전용`과 `Redis + DB` 경로를 한 화면에서 비교한다.
- 필요 시 `Redis Only`를 참고선으로 함께 보여줄 수 있어야 한다.
- 같은 시나리오를 같은 조건으로 반복 실행할 수 있어야 한다.
- 평균 지연시간뿐 아니라 적중률, 성능 역전 기준 적중률, 오류, TTL 설정값과 cache writeback/fallback 흐름을 함께 보여준다.
- `mini-redis`가 현재 지원하는 명령 범위 안에서만 동작해야 한다.
- UI가 도메인 KPI와 요청 요약 계산을 직접 떠안지 않고, 실행 엔진이 계산한 결과를 읽기 쉽게 보여주는 구조여야 한다.
- 단, replay 진행률이나 선택 상태처럼 화면 표현을 위한 경량 파생 상태는 프론트엔드가 가공할 수 있어야 한다.
- 발표용 시스템이므로 백엔드는 가능한 한 얇게 유지해야 한다.
- 정적인 이미지 대신 시간축 기반 처리 흐름 UI로 요청 경로를 직관적으로 보여줘야 한다.

## 4. 비목표

이번 단계에서 하지 않는 일은 아래와 같다.

- `mini-redis` 자체를 수정해서 기능을 추가하지 않는다.
- 분산 캐시, 복제, 영속성, 샤딩, 클러스터를 구현하지 않는다.
- 운영용 모니터링 시스템처럼 범용 대시보드를 만들지 않는다.
- 모든 Redis 자료구조를 동시에 시연하지 않는다.
- 무거운 별도 운영 백엔드 서비스를 만들지 않는다.

## 5. 대상 시스템 전제

현재 `mini-redis` 기준으로 설계에 반영해야 하는 전제는 아래와 같다.

- 로컬 기본 주소는 `127.0.0.1:6379`다.
- 인메모리 서버이며 데이터 영속성이 없다.
- `SET`, `GET`, `DEL`, `EXPIRE`, `TTL`은 1차 시나리오에 적합하다.
- `mini-redis`는 RESP 기반으로 동작하며, 현재 벤치마크 앱은 `redis-py`가 아니라 raw socket 기반 커스텀 RESP 클라이언트로 연결한다.
- 세션 단위 요청 처리가 가능하지만, 발표용 시스템은 복잡한 장기 연결보다 재현 가능한 실행을 우선해야 한다.

baseline 데이터 소스 전제는 아래와 같다.

- 1차 benchmark baseline은 실제 로컬 MongoDB를 조회 대상으로 사용한다.
- baseline DB는 `record_id`, `title`, `body`를 가진 문서 collection을 사용한다.
- 로컬 설정 파일과 환경 변수로 MongoDB 연결 정보를 주입한다.
- 시드 데이터는 저장소 안의 JSON 파일에서 읽어 upsert 방식으로 준비한다.

## 6. 대표 시나리오

### 6-1. 1차 시나리오

첫 버전은 `상세 페이지 반복 조회` 시나리오 하나에 집중한다.

선정 이유:

- cache hit/miss 차이를 설명하기 쉽다.
- `GET` 중심이라 현재 `mini-redis` 능력과 잘 맞는다.
- TTL 만료 후 재조회 흐름을 함께 보여주기 좋다.

### 6-2. 확장 시나리오

1차 시나리오가 안정화되면 아래를 추가한다.

- 검색 자동완성 집중 부하
- 인기 데이터 반복 조회
- 콜드 캐시와 웜 캐시 혼합 워크로드

## 7. 상위 아키텍처

전체 흐름은 아래와 같다.

`Dashboard UI -> Benchmark API -> Scenario Runner -> Baseline Service / Cache Service -> mini-redis + Data Source -> Metrics Aggregator -> Result Store`

이 구조에서 중요한 점은 "실행", "계산", "표시"를 분리하는 것이다.

### 7-1. 백엔드 단순화 원칙

이 시스템은 가급적 별도 대형 백엔드를 만들지 않는다.

권장 방식은 아래 둘 중 하나다.

- 같은 프로세스 안의 얇은 로컬 API 계층
- UI가 직접 호출하는 로컬 benchmark runner

어떤 방식을 택하더라도 역할은 동일하다.

- benchmark 실행 시작
- 현재 상태 조회
- 결과 조회
- 로그 조회

즉, 이 계층은 운영 서비스가 아니라 발표용 실행 컨트롤러다.

### 7-2. 연결 아키텍처 원칙

프론트엔드와 백엔드는 1차 버전에서 same-origin 구성을 기본값으로 둔다.

권장 연결 방식:

- 백엔드가 `GET /` 에서 프론트 정적 번들을 함께 서빙한다.
- 프론트는 기본 API base를 `/api` 로 사용한다.
- 브라우저에서 대시보드를 열었을 때 추가 프록시 설정 없이 바로 동작하는 구성을 우선한다.

보조 연결 방식:

- 교차 origin 개발 서버 사용
- reverse proxy 사용
- 제한적인 CORS 허용

현재 구현 메모:

- 백엔드는 `app/ui/static` 기준 정적 파일을 same-origin으로 서빙할 수 있다.
- 기본 `OPTIONS` 응답과 `Access-Control-Allow-Origin: *` 헤더를 제공한다.
- 이 CORS 정책은 로컬 개발 편의를 위한 기본값이며, 운영용 보안 정책으로 간주하지 않는다.

## 8. 컴포넌트 설계

### 8-1. Dashboard UI

역할:

- 실행 옵션 입력
- 진행 상태 표시
- KPI 및 차트 렌더링
- 실행 로그 표시
- 시간축 처리 흐름 렌더링

필수 영역:

- 시나리오 요약
- 메인 비교 그래프
- `DB 전용`, `Redis 적중`, `Redis 미스` 분리 KPI 카드
- 실시간 처리 흐름 레인 뷰
- 최소 lane summary

보조 영역:

- `Redis Only` 참고선 토글
- 최근 요청 경로 설명 패널
- 이벤트 로그 콘솔
- 최근 run 목록
- 요청 분포 또는 stage 집계 차트

현재 1차 프론트 데이터 소스 원칙:

- run 상태와 로그: `GET /api/benchmark-runs/:id`
- request detail, lane token, replay 기본 데이터: `GET /api/benchmark-runs/:id/requests`
- KPI, lane summary, 차트 시리즈: `GET /api/benchmark-runs/:id/presentation`
- raw event stream: 디버깅, 계약 검증, 후속 확장용 원본 데이터

### 8-1A. 시간축 흐름 UI 설계

이 UI는 단순 차트나 정적 이미지가 아니라, benchmark 이벤트를 바탕으로 실제 요청 처리를 시간축 위에 재구성하는 뷰다.

핵심 구성:

- `DB Only` lane
- `Redis + DB` lane
- 선택적 `Redis Only reference` lane
- 요청 이벤트 마커
- 단계별 상태 색상
- 실시간 또는 재생형 애니메이션

표현 원칙:

- `DB Only`는 `App -> DB -> Response` 흐름을 단순하게 보여준다.
- `Redis hit`는 짧고 빠른 경로로 표시한다.
- `Redis miss`는 `App -> Redis -> DB -> Redis -> Response` 흐름으로 표시한다.
- fallback, 오류는 별도 강조 마커로 보여주고, TTL은 1차 버전에서는 설정값과 writeback 흐름으로 설명한다.

현재 구현 메모:

- 1차 프론트는 raw `events[]`를 직접 레인 렌더링의 주 데이터로 쓰지 않는다.
- 레인 보드와 request 상세 패널은 `request timeline read model`을 우선 사용한다.
- replay는 request timeline 배열 순서와 request 내부 상대 duration을 사용해 재생한다.

### 8-1B. 화면 레이아웃 상세

권장 레이아웃은 아래와 같다.

1. 헤더 영역
- 현재 시나리오 이름
- `mini-redis` 연결 상태
- 실행 중 여부
- 마지막 실행 시각

2. 제어 패널
- scenario selector
- iteration count
- concurrency
- ttl seconds
- hit rate buckets
- run / replay 버튼

`stop`은 후속 제어 API가 준비되면 추가하는 선택 기능으로 둔다.
`concurrency`는 1차 버전에서 실험 설정 저장과 표시를 위한 입력이며, 실제 실행 엔진은 순차 모드로 먼저 고정한다.

3. KPI 영역
- `DB Only Avg`
- `Redis Hit Avg`
- `Redis Miss Avg`
- `Speedup`
- `Break-even Hit Rate`
- `Cache Hit Rate`
- `Error Count`

4. 메인 시각화 영역
- 최상단: `DB Only`, `Redis Hit`, `Redis Miss`를 나란히 비교하는 핵심 그래프
- 하단: 시간축 흐름 lane view

5. 하단 디버그 영역
- 이벤트 로그 콘솔
- 선택한 request 상세 패널

### 8-1C. 흐름 레인 구성

lane view는 아래 레인을 가진다.

- `DB Only`
- `Redis + DB`
- 선택적 `Redis Only Reference`

각 lane은 동일한 playback 축을 공유한다.

1차 버전에서는 이벤트 배열 순서를 공통 축으로 사용하고, request 내부 단계 시간은 상대 ms로 표현한다.

각 request는 하나의 flow token으로 표현한다.

token 표현 규칙:

- 기본 형태: 원형 또는 캡슐형 pulse
- 색상:
  - `DB Only`: amber
  - `Redis hit`: emerald
  - `Redis miss`: blue
  - `fallback`: orange
  - `error`: red
- 강조:
  - 현재 선택된 request는 외곽선과 확대 효과
  - 최근 1초 이내 이벤트는 glow 효과

### 8-1D. request 상세 패널

사용자가 특정 token 또는 이벤트를 클릭하면 아래를 표시한다.

- request id
- mode
- request sequence 또는 시작 offset
- total duration
- cache status
- path summary
- stage별 duration
- error 여부

예시 path summary:

- `DB Only: App -> DB -> Response`
- `Redis + DB hit: App -> Redis -> Response`
- `Redis + DB miss: App -> Redis -> DB -> Redis -> Response`

### 8-1E. 시각화 모드

UI는 두 가지 시각화 모드를 지원하는 것이 좋다.

- `Live`: benchmark 실행 중 실시간 반영
- `Replay`: 완료된 run을 축약된 속도로 다시 재생

Replay 모드는 발표할 때 특히 유용하다.

이유:

- 실제 요청이 너무 빨라서 눈에 안 보이는 문제를 줄일 수 있다.
- 같은 run을 청중에게 반복 설명할 수 있다.

1차 버전에서는 별도 replay API 없이 저장된 event stream을 클라이언트가 다시 재생하는 방식으로 충분하다.

### 8-2. Benchmark API

역할:

- 새로운 benchmark run 생성
- 현재 run 상태 조회
- 이벤트 로그 조회
- 최종 결과 반환

필수 엔드포인트 예시:

- `POST /api/benchmark-runs`
- `GET /api/benchmark-runs/:id`
- `GET /api/benchmark-runs/:id/events`
- `GET /api/benchmark-runs/:id/requests`
- `GET /api/benchmark-runs/:id/presentation`
- `GET /api/health`

이 계층은 최소 기능만 담당한다.

- 인증 없음
- 사용자 개념 없음
- run history는 파일 또는 로컬 저장소 기준
- 한 번에 하나의 benchmark run만 수행해도 충분

현재 구현 메모:

- 1차 구현은 `ThreadingHTTPServer`와 파일 기반 run store를 사용한다.
- 활성 run 중복 방지는 제공하지만, 완전한 원자적 single-flight 보장은 후속 보강 과제로 둔다.
- `GET /` 와 정적 파일 same-origin 서빙을 지원한다.
- 기본 `OPTIONS` 응답과 단순 CORS 헤더를 제공한다.

### 8-2A. API 응답 상세

`POST /api/benchmark-runs` 응답 예시:

```json
{
  "run_id": "run_20260318_001",
  "status": "queued",
  "scenario": "detail_page",
  "created_at": "2026-03-18T02:20:00Z"
}
```

`GET /api/benchmark-runs/:id` 응답 예시:

```json
{
  "run_id": "run_20260318_001",
  "status": "completed",
  "summary": {
    "db_avg_ms": 182.4,
    "redis_avg_ms": 24.1,
    "speedup_ratio": 7.57,
    "break_even_hit_rate": 35,
    "cache_hit_rate": 62,
    "error_count": 0
  }
}
```

`GET /api/benchmark-runs/:id/events` 응답 예시:

```json
{
  "run_id": "run_20260318_001",
  "events": [
    {
      "event_id": "evt_001",
      "request_id": "req_184",
      "timestamp": 120,
      "mode": "cache_aside",
      "event_type": "cache_miss",
      "stage": "redis_lookup",
      "duration_ms": 3,
      "metadata": {
        "key": "benchmark:detail:42"
      }
    }
  ]
}
```

이벤트 조회 제약:

- 현재 `after` 필터는 request 상대 `timestamp` 기준이라 엄밀한 증분 스트리밍 커서로는 부정확하다.
- 1차 프론트엔드는 전체 이벤트 재조회 후 `event_id` 기준 dedupe를 우선한다.

### 8-2B. Frontend Support Read Model

시간축 흐름 UI와 request 상세 패널은 raw `events[]`만으로도 구현할 수 있지만, 1차 버전에서는 프론트 복잡도를 줄이기 위해 프론트 지원용 집계 read model을 함께 제공한다.

역할:

- event stream을 `request_id` 기준으로 묶는다.
- request 단위 `path_summary`, `cache_status`, `stage_durations`, `total_duration_ms`를 계산한다.
- request 상세 패널과 lane token 설명에 바로 사용할 수 있는 응답 형태를 제공한다.
- KPI 카드, lane summary, 차트 series를 프론트가 직접 재계산하지 않도록 발표 화면용 집계 응답을 제공한다.

설계 원칙:

- raw `events[]`는 디버깅과 후속 확장을 위한 원천 데이터로 유지한다.
- 프론트의 주요 화면은 `requests`, `presentation` read model을 우선 사용한다.
- 프론트는 read model을 받아 화면 상태와 replay 진행률 같은 표현용 상태만 계산한다.

1차 권장 API:

- `GET /api/benchmark-runs/:id/requests`
- `GET /api/benchmark-runs/:id/presentation`

이 read model은 새로운 원천 데이터를 만들지 않는다.

- 원천 데이터는 여전히 `events[]`다.
- `request timeline read model`은 저장된 event stream을 프론트 친화적인 request timeline 뷰로 재구성한 결과다.
- `presentation read model`은 run summary와 event stream을 함께 사용해 KPI, lane summary, 차트용 series를 만든 결과다.

`request timeline read model` 역할:

- request detail panel 지원
- lane token hover/click 설명 지원
- path summary와 stage duration 계산 지원
- replay의 기본 데이터 소스 제공

`presentation read model` 역할:

- KPI 카드 데이터 제공
- lane summary 카드 데이터 제공
- latency comparison 차트 시리즈 제공
- path ratio 차트 시리즈 제공
- stage 누적량 차트 시리즈 제공

현재 1차 프론트 연결 방향:

- `requests` 는 시각화의 주 데이터 소스다.
- `presentation` 은 상단 KPI와 보조 차트의 주 데이터 소스다.
- `events` 는 원본 검증, 계약 점검, 후속 실시간 스트리밍 확장용 보조 소스다.

### 8-3. Scenario Runner

역할:

- 시나리오를 고정된 파라미터로 실행
- `DB 전용`과 `Redis + DB`를 동일 조건으로 실행
- 워밍업, 본 실행, 결과 수집을 분리

입력:

- `scenario`
- `iteration_count`
- `concurrency`
- `hit_rate_buckets`
- `ttl_seconds`

출력:

- raw latency samples
- cache hit/miss 기록
- 이벤트 로그
- 집계 대상 메트릭
- 시간축 렌더링용 이벤트 스트림

### 8-3A. 실행 상태 머신

run 상태는 아래 상태를 가진다.

- `queued`
- `bootstrapping`
- `warming_up`
- `running_baseline`
- `running_cache`
- `running_reference`
- `aggregating`
- `completed`
- `failed`

request 상태는 아래 상태를 가진다.

- `started`
- `cache_lookup`
- `cache_hit`
- `cache_miss`
- `db_lookup`
- `cache_writeback`
- `responded`
- `errored`

### 8-4. Baseline Service

역할:

- 캐시를 사용하지 않는 비교 기준 경로
- 느리지만 일관된 응답 제공

설계 원칙:

- 1차 구현은 실제 로컬 MongoDB를 baseline DB로 사용한다.
- 응답 스키마는 cache 경로와 완전히 같아야 한다.
- baseline client는 `record_id` 기준 단건 조회를 수행한다.
- 시드 데이터는 upsert 방식으로 보정 가능해야 한다.

요청 경로:

- `App -> DB`

현재 1차 baseline DB 설정:

- backend type: `mongodb`
- 기본 URI: `mongodb://127.0.0.1:27017`
- 기본 DB: `mini_redis_benchmark`
- 기본 collection: `detail_pages`
- 기본 seed 파일: `data/mongodb/detail_page_seed.json`

설정 주입 방식:

- `APP_SETTINGS_FILE=config/mongodb.local.json`
- 또는 `BASELINE_BACKEND`, `MONGODB_URI`, `MONGODB_DB_NAME`, `MONGODB_COLLECTION`, `MONGODB_SEED_FILE` 환경 변수

후속 확장 옵션:

- 로컬 MongoDB 대신 MongoDB Atlas 같은 원격 MongoDB를 baseline DB로 사용할 수 있다.
- 이 경우 `MONGODB_URI`에 원격 connection string을 주입하고, IP 허용 목록, TLS, 계정 권한, 네트워크 지연을 함께 관리해야 한다.
- 발표/리허설의 재현성을 우선할 때는 로컬 MongoDB가 기본값이고, 운영 유사성 검증이 필요할 때만 원격 DB 모드를 별도 리허설 시나리오로 분리하는 것이 좋다.

### 8-5. Cache Service

역할:

- `mini-redis`를 사용하는 앱 경로
- cache hit, miss, fallback, TTL 동작을 기록

설계 원칙:

- `mini-redis` 호출은 전용 adapter로 캡슐화한다.
- 앱 레이어는 raw RESP를 직접 다루지 않는다.
- key 규칙은 시나리오 prefix를 반드시 포함한다.

요청 경로는 아래 두 경우로 나뉜다.

- hit: `App -> Redis`
- miss: `App -> Redis -> DB -> Redis`

예시:

- `benchmark:detail:{entity_id}`

### 8-6. mini-redis Adapter

역할:

- `mini-redis`와 실제 통신
- 지원 명령 범위 통제
- 오류를 앱 레벨 예외로 변환

1차 지원 메서드:

- `get(key)`
- `set(key, value)`
- `delete(key)`
- `expire(key, seconds)`
- `ttl(key)`

1차 구현 제약:

- 기본 대상 주소는 `127.0.0.1:6379`다.
- host/port 변경 가능한 설정 주입은 후속 단계에서 확장한다.

### 8-6A. Redis Only Reference Mode

역할:

- 메인 비교축이 아닌 참고용 성능 상한선을 제공한다.

설계 원칙:

- 이 모드는 별도 카드보다 보조 차트 또는 참고선으로 우선 표시한다.
- 청중이 실서비스 경로와 혼동하지 않도록 `reference` 라벨을 붙인다.

### 8-7. Metrics Aggregator

역할:

- raw sample을 모아서 발표용 KPI 계산
- 차트 series와 요약 카드 데이터를 동시에 생성

필수 계산값:

- `db_avg_ms`
- `redis_avg_ms`
- `p95_db_ms`
- `p95_redis_ms`
- `speedup_ratio`
- `improvement_percent`
- `break_even_hit_rate`
- `cache_hit_rate`
- `error_count`

그래프용 계산값:

- 시간 흐름별 latency series
- hit rate bucket별 latency series
- 모드별 요청 수 또는 경로 비율

흐름 UI용 계산값:

- request별 시작 시각
- request별 종료 시각
- request별 mode
- request별 cache status
- request별 path stages
- stage별 duration

프론트 지원용 집계 read model:

- request timeline 목록
- request별 path summary
- request별 total duration
- request별 error 여부
- request별 정규화된 원본 event 배열
- KPI 카드용 요약 값
- lane summary 목록
- latency comparison 시리즈
- path ratio 시리즈
- timeline stage totals 시리즈

### 8-7A. 성능 역전 기준 계산 규칙

성능 역전 기준 적중률은 아래 기준으로 계산한다.

1. hit rate bucket별로 `Redis + DB` 평균 지연시간을 구한다.
2. 같은 시나리오의 `DB Only` 평균 지연시간과 비교한다.
3. `Redis + DB 평균 지연시간 <= DB Only 평균 지연시간`이 처음 성립하는 bucket을 찾는다.
4. 해당 bucket을 `break_even_hit_rate`로 저장한다.

버킷 사이 보간은 1차 버전에서 생략 가능하다.

### 8-7B. 요청 경로 집계 규칙

모드별로 아래 카운트를 유지한다.

- `db_only_count`
- `redis_hit_count`
- `redis_miss_count`
- `fallback_count`
- `error_count`

이 값들은 lane summary와 보조 차트에 재사용한다.

### 8-8. Result Store

역할:

- benchmark run 결과 저장
- 새로고침 후에도 결과 재조회 가능

1차 권장안:

- 파일 기반 JSON 저장 또는 SQLite

baseline DB 보조 파일:

- `config/mongodb.local.json`
- `data/mongodb/detail_page_seed.json`
- `scripts/seed_mongodb.py`

## 9. 데이터 모델

### 9-1. Benchmark Run

필수 필드:

- `run_id`
- `scenario`
- `status`
- `started_at`
- `finished_at`
- `iteration_count`
- `concurrency`
- `hit_rate_buckets`
- `ttl_seconds`
- `mini_redis_commit`
- `app_commit`

### 9-2. Result Summary

필수 필드:

- `db_avg_ms`
- `redis_avg_ms`
- `p95_db_ms`
- `p95_redis_ms`
- `speedup_ratio`
- `improvement_percent`
- `break_even_hit_rate`
- `cache_hit_rate`
- `error_count`

### 9-3. Event Log

필수 필드:

- `timestamp`
- `level`
- `stage`
- `message`
- `metadata`

예시 stage:

- `bootstrap`
- `warmup`
- `baseline_run`
- `cache_run`
- `reference_run`
- `aggregation`
- `complete`
- `failed`

### 9-4. Flow Event Model

시간축 UI 렌더링을 위해 아래 이벤트 모델을 사용한다.

필수 필드:

- `event_id`
- `request_id`
- `timestamp`
- `mode`
- `event_type`
- `stage`
- `duration_ms`
- `metadata`

표현 규칙:

- 이벤트 배열 순서는 benchmark 기록 순서를 보존한다.
- `timestamp`는 request 시작 이후 경과 ms다.
- 공통 lane playback 축은 이벤트 배열 순서와 request 내부 상대 시간의 조합으로 재구성한다.

권장 `event_type`:

- `request_started`
- `cache_lookup_started`
- `cache_lookup_completed`
- `cache_hit`
- `cache_miss`
- `db_query_started`
- `db_query_completed`
- `cache_set`
- `response_sent`
- `fallback_used`
- `error`

`ttl_expired`는 TTL 만료를 강제로 시뮬레이션하는 시나리오에서 선택적으로 추가한다.

### 9-5. Flow Event Example

`Redis + DB miss` 예시:

```json
[
  {
    "event_id": "evt_101",
    "request_id": "req_77",
    "timestamp": 0,
    "mode": "cache_aside",
    "event_type": "request_started",
    "stage": "request",
    "duration_ms": 0,
    "metadata": {
      "path": "/detail/42"
    }
  },
  {
    "event_id": "evt_102",
    "request_id": "req_77",
    "timestamp": 2,
    "mode": "cache_aside",
    "event_type": "cache_miss",
    "stage": "redis_lookup",
    "duration_ms": 2,
    "metadata": {
      "key": "benchmark:detail:42"
    }
  },
  {
    "event_id": "evt_103",
    "request_id": "req_77",
    "timestamp": 18,
    "mode": "cache_aside",
    "event_type": "db_query_completed",
    "stage": "db_lookup",
    "duration_ms": 16,
    "metadata": {
      "record_id": 42
    }
  },
  {
    "event_id": "evt_104",
    "request_id": "req_77",
    "timestamp": 21,
    "mode": "cache_aside",
    "event_type": "cache_set",
    "stage": "writeback",
    "duration_ms": 3,
    "metadata": {
      "ttl_seconds": 30
    }
  },
  {
    "event_id": "evt_105",
    "request_id": "req_77",
    "timestamp": 24,
    "mode": "cache_aside",
    "event_type": "response_sent",
    "stage": "response",
    "duration_ms": 0,
    "metadata": {
      "status": "ok"
    }
  }
]
```

## 10. 실행 흐름

1. 사용자가 UI에서 시나리오와 실행 옵션을 선택한다.
2. Benchmark API가 run을 생성한다.
3. 시스템이 `mini-redis` health check를 수행한다.
4. 워밍업을 실행한다.
5. `Redis + DB` run 내부에서 bucket별 key priming 또는 eviction으로 hit/miss 조건을 만든다.
6. `DB 전용` benchmark를 실행한다.
7. `Redis + DB` benchmark를 실행한다.
8. 필요 시 `Redis Only` 참고 결과를 실행하거나 기존 reference 데이터를 불러온다.
9. 결과를 집계한다.
10. UI가 이벤트 스트림을 받아 시간축 흐름 UI를 렌더링한다.
11. UI가 KPI, 차트, 로그를 함께 렌더링한다.

비고:

- 현재 이벤트 playback 기준 chronology는 run 전체 절대 시각이 아니라 이벤트 배열 순서와 request 상대 시간의 조합이다.

## 10-1. 시각화 전략

청중에게는 아래 순서로 보여주는 것이 가장 직관적이다.

1. `DB Only`, `Redis Hit`, `Redis Miss`를 분리한 첫 비교 그래프
2. 시간축 처리 흐름 UI
3. `DB Only`, `Redis Hit`, `Redis Miss` KPI 카드
4. 필요 시 요청 경로 설명
5. 필요 시 이벤트 로그 또는 보조 차트

이 순서는 "핵심 결론 -> 왜 그런지 -> 보조 근거" 흐름을 만든다.

## 10-2. 애니메이션 원칙

- 애니메이션은 장식이 아니라 처리 경로 설명을 위한 용도로만 사용한다.
- 너무 빠른 요청도 최소 가시 시간을 가져야 한다.
- `hit`, `miss`, `fallback`, `error`는 색과 모션으로 명확히 구분한다.
- 이벤트 스트림 재생 속도는 실제 시간 비례 또는 축약 재생 모드를 둘 수 있다.

추가 원칙:

- 같은 request의 이벤트는 동일한 token id로 묶어서 이동시킨다.
- lane 사이 점프는 stage 전이 시에만 일어난다.
- 지나간 token은 완전히 사라지지 않고 짧은 꼬리 흔적을 남길 수 있다.
- 너무 많은 요청이 동시에 보이면 sampling 또는 aggregation view로 전환한다.

## 10-3. 프론트 구현 방식

권장 방식:

- 일반 KPI/차트는 차트 라이브러리 사용
- 처리 흐름 UI는 SVG 또는 Canvas 기반 커스텀 렌더링

이유:

- 일반 차트는 라이브러리로 빠르게 구현 가능하다.
- 시간축 레인, 요청 펄스, 단계별 전이 표현은 커스텀 렌더링이 더 적합하다.

### 10-3A. 프론트 상태 모델

권장 상태 구조:

- `runConfig`
- `runStatus`
- `summaryMetrics`
- `eventStream`
- `selectedRequestId`
- `playbackMode`
- `playbackSpeed`
- `laneFilters`

### 10-3B. 렌더링 파이프라인

권장 파이프라인:

1. raw event 수신
2. request id 기준 그룹핑
3. stage timeline 계산
4. lane position 계산
5. animation frame model 생성
6. SVG 또는 Canvas 렌더

### 10-3C. 성능 최적화 원칙

- 이벤트 배열은 append-only 구조를 우선 사용한다.
- request detail 계산은 선택된 request에 대해서만 자세히 수행한다.
- 전체 token 수가 많아지면 최근 window만 실시간 렌더한다.
- 과거 이벤트는 요약 모드 또는 replay 데이터로 분리한다.

## 10-4. 컴포넌트 구조 예시

```text
BenchmarkPage
  BenchmarkHeader
  BenchmarkControls
  PrimaryLatencyComparisonChart
  KpiSummaryGrid
  FlowLaneBoard
    FlowLane
    FlowToken
    FlowCursor
  SupportingChartsDrawer
    HitRateCurveChart
    PathRatioChart
  SupportingDebugDrawer
    EventLogPanel
    RequestDetailPanel
```

## 10-5. 구현 우선순위

1. KPI 카드
2. Flow Event Model 수집
3. 2-lane 흐름 UI
4. request detail panel
5. latency comparison chart
6. hit rate curve chart
7. replay mode

이 순서가 좋은 이유는, 핵심 설득력은 흐름 UI와 KPI에서 먼저 나오고 나머지는 그 다음에 붙여도 되기 때문이다.

## 11. 실패 처리 설계

반드시 구분해 보여줘야 하는 실패는 아래와 같다.

- `mini-redis` 미기동
- 연결 실패
- 지원하지 않는 명령 호출
- TTL 설정 실패
- 집계 실패

실패 시에도 UI는 아래를 유지해야 한다.

- 실패 단계 표시
- 실행 옵션 표시
- 부분 로그 표시
- fallback 여부 표시

## 12. 관측 설계

필수 로그 이벤트:

- benchmark queue 등록 또는 시작
- health check 성공/실패
- warmup 시작/완료
- baseline run 시작/완료
- cache run 시작/완료
- reference run 시작/완료
- 집계 시작/완료
- 오류 발생

필수 KPI:

- 평균 지연시간
- `Redis Hit` 평균 지연시간
- `Redis Miss` 평균 지연시간
- 속도 향상 배수
- 성능 역전 기준 적중률
- 캐시 적중률
- 오류 수

보조 집계:

- `p95_db_ms`
- `p95_redis_ms`
- `p95_reference_ms`
- `improvement_percent`

비고:

- 위 보조 집계는 run summary와 API 계약에는 포함되지만, 현재 1차 프론트의 상단 KPI 카드와 발표용 차트는 평균 지표 중심으로 노출한다.

필수 시각화:

- 시간축 기반 처리 흐름 UI
- `DB Only`, `Redis Hit`, `Redis Miss` 지연시간 비교 차트

선택 시각화:

- 적중률 대비 평균 지연 차트
- 시간 경과별 지연 변화 차트
- `DB`, `Redis hit`, `Redis miss` 경로 비율 차트

## 13. 설계 결정 요약

이번 설계의 핵심 결정은 아래와 같다.

- 첫 버전은 `상세 조회` 시나리오 하나에 집중한다.
- benchmark 계산은 실행 엔진에서만 수행한다.
- UI는 실행과 결과 설명에 집중한다.
- 메인 비교는 `DB Only`와 `Redis + DB`다.
- `Redis Only`는 참고용 reference 모드로만 사용한다.
- 단순 그래프보다 시간축 기반 흐름 UI가 핵심 시각화다.
- 차트와 흐름 UI는 함께 사용한다.
- 백엔드는 가능하면 별도 서비스가 아니라 로컬 실행 제어 계층으로 제한한다.
- `mini-redis`는 adapter 뒤에 숨긴다.
- 결과는 반복 가능한 run 단위 산출물로 저장한다.

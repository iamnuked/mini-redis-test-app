# mini-redis 벤치마크 UI 및 시스템 요구사항 정의서

## 1. 문서 목적

이 문서는 `mini-redis`를 청중에게 시연하기 위한 벤치마크 UI 및 시스템이 반드시 만족해야 하는 기능 요구사항, 비기능 요구사항, 제약사항, 완료 기준을 정의한다.

이 문서는 설계 문서보다 앞선 기준 문서이며, 구현 범위 판단의 기준점으로 사용한다.

## 2. 배경

현재 팀은 `.tmp/mini-redis-dev`에 있는 `mini-redis` `dev` 브랜치를 테스트 대상으로 사용하고 있다.

이 시스템의 목적은 아래를 직관적으로 보여주는 것이다.

- `DB 전용` 경로와 `Redis + DB` 경로의 차이
- `Redis Only`가 낼 수 있는 참고 성능 상한선
- 캐시 적중률이 성능에 어떤 영향을 주는지
- TTL, fallback, 오류 상황이 어떻게 동작하는지

단순 로그나 평균값만으로는 발표 대상이 흐름을 이해하기 어렵기 때문에, 시각적 UI와 재현 가능한 benchmark 실행 체인이 함께 필요하다.

## 3. 목표 사용자

### 3-1. 1차 사용자

- 발표자
- 데모를 보는 청중
- 시스템을 구현하는 개발팀

### 3-2. 사용자 기대

- 발표자는 같은 조건으로 benchmark를 다시 실행할 수 있어야 한다.
- 청중은 어떤 상황에서 Redis 경로가 빨라지는지 바로 이해할 수 있어야 한다.
- 개발팀은 benchmark 결과를 재현하고 디버깅할 수 있어야 한다.

## 4. 제품 목표

- 하나의 대표 시나리오를 기준으로 `DB 전용`과 `Redis + DB`를 명확히 비교한다.
- 필요 시 `Redis Only`를 참고용 비교선으로 표시할 수 있다.
- benchmark 실행 상태, 결과 수치, 이벤트 로그를 한 화면에서 보여준다.
- 결과는 반복 실행 가능하고 재현 가능해야 한다.
- 현재 `mini-redis` 지원 범위를 벗어나지 않고 데모가 동작해야 한다.
- 백엔드는 발표용 실행 제어에 필요한 최소 수준으로 유지해야 한다.

## 5. 범위

### 5-1. 1차 포함 범위

- 대표 시나리오 1개
- benchmark 실행 API
- 실행 상태 확인
- 결과 요약 KPI
- 지연 시간 시각화
- 적중률 대비 지연 시각화
- 시간축 기반 요청 처리 흐름 시각화
- 이벤트 로그 표시
- `mini-redis` health check
- `SET`, `GET`, `DEL`, `EXPIRE`, `TTL` 기반 캐시 경로
- 로컬 MongoDB 기반 baseline DB 경로

### 5-2. 1차 제외 범위

- 모든 Redis 자료구조 시연
- 다중 사용자 환경
- 운영용 인증/권한
- 클러스터링, 복제, 영속성
- 범용 APM/모니터링 플랫폼 수준 기능
- 무거운 별도 운영 백엔드 서비스
- MongoDB Atlas 같은 원격 DB를 기본 리허설 경로로 강제하지 않는다.

## 6. 핵심 사용자 시나리오

### 6-1. 시나리오 A. 발표자가 benchmark를 실행한다

1. 발표자가 UI에서 시나리오와 실행 옵션을 선택한다.
2. 시스템이 `mini-redis` 연결 상태를 점검한다.
3. 시스템이 `DB 전용`과 `Redis + DB` benchmark를 같은 조건으로 실행한다.
4. 필요 시 `Redis Only` 참고 결과를 함께 표시한다.
5. UI가 진행 상태와 이벤트 로그를 보여준다.
6. 완료 후 KPI와 시간축 기반 시각화 UI를 표시한다.

성공 조건:

- 실행 실패 여부가 명확히 표시된다.
- 결과 수치와 로그가 함께 남는다.

### 6-2. 시나리오 B. 청중이 결과를 해석한다

1. 청중은 두 경로의 평균 지연시간을 비교한다.
2. 청중은 속도 향상 배수와 개선율을 확인한다.
3. 청중은 성능 역전 기준 적중률을 확인한다.
4. 청중은 요청이 `DB`, `Redis`, `Redis -> DB` 중 어떤 경로를 탔는지 시간축 흐름으로 이해한다.
5. 청중은 로그를 통해 실제 실행 과정과 오류 여부를 이해한다.

성공 조건:

- 한 화면만 봐도 결과 의미를 이해할 수 있다.

### 6-3. 시나리오 C. 개발자가 문제를 디버깅한다

1. 개발자가 benchmark 실행 실패를 확인한다.
2. 시스템이 실패 단계와 이벤트 로그를 보여준다.
3. 개발자는 연결 실패, 명령 실패, 집계 실패를 구분할 수 있다.

성공 조건:

- 실패 원인이 숨지 않고 드러난다.

## 7. 기능 요구사항

### FR-1. benchmark 실행

시스템은 사용자가 benchmark run을 새로 시작할 수 있게 해야 한다.

최소 입력:

- `scenario`
- `iteration_count`
- `concurrency`
- `hit_rate_buckets`
- `ttl_seconds`

비고:

- `concurrency`는 실험 설정과 결과 메타데이터에 포함해야 한다.
- 1차 버전 실행 엔진은 순차 실행을 기준으로 하며, 실제 병렬 실행은 후속 단계에서 확장한다.

### FR-2. health check

시스템은 benchmark 실행 전에 `mini-redis` 연결 가능 여부를 확인해야 한다.

### FR-3. baseline 경로 지원

시스템은 캐시를 사용하지 않는 `DB 전용` 경로를 제공해야 한다.

1차 구현에서 baseline 경로는 실제 로컬 MongoDB 단건 조회를 사용해야 한다.

### FR-4. cache 경로 지원

시스템은 `mini-redis`를 사용하는 `Redis + DB` 경로를 제공해야 한다.

### FR-4A. 참고용 Redis Only 모드

시스템은 선택적으로 `Redis Only` 결과를 참고선 또는 보조 모드로 표시할 수 있어야 한다.

이 모드는 메인 비교축이 아니라 참고용 결과로 취급한다.

### FR-5. 지원 명령 범위 통제

시스템은 1차 버전에서 아래 명령만 안정 경로로 사용해야 한다.

- `SET`
- `GET`
- `DEL`
- `EXPIRE`
- `TTL`

### FR-6. 동일 조건 비교

시스템은 `DB 전용`과 `Redis + DB` benchmark를 동일한 시나리오, 반복 횟수, 적중률 bucket 구성, TTL 설정, 입력 데이터 기준으로 실행해야 한다.

1차 버전에서는 두 경로를 모두 순차 실행 기준으로 맞추고, `concurrency` 값은 실행 메타데이터와 UI 입력으로 유지한다.

### FR-7. 워밍업 분리

시스템은 워밍업 실행과 본 실행을 구분해야 한다.

### FR-7A. 상태 준비 방식

1차 대표 시나리오는 별도 전역 seed 단계를 필수로 두지 않는다.

- warmup은 baseline 데이터 경로를 미리 데우는 용도로 사용한다.
- baseline DB 자체는 시드 JSON 기반 upsert 방식으로 준비할 수 있어야 한다.
- cache hit/miss 조건은 cache run 내부의 key priming 또는 eviction으로 만든다.
- 독립 seed 단계는 시나리오 확장 시 선택적으로 추가할 수 있다.

### FR-8. 결과 집계

시스템은 최소 아래 결과를 계산해야 한다.

- `db_avg_ms`
- `redis_hit_avg_ms`
- `redis_miss_avg_ms`
- `redis_avg_ms`
- `p95_db_ms`
- `p95_redis_ms`
- `speedup_ratio`
- `improvement_percent`
- `break_even_hit_rate`
- `cache_hit_rate`
- `error_count`

비고:

- `redis_hit_avg_ms`, `redis_miss_avg_ms`는 사용자가 실제로 궁금해하는 "Redis만 다녀온 경우"와 "Redis 미스로 DB까지 간 경우"를 분리해서 보여주기 위한 핵심 집계다.
- `p95_db_ms`, `p95_redis_ms`, `improvement_percent`는 현재 run summary와 API 계약에 포함해야 한다.
- 다만 1차 프론트의 상단 KPI 카드와 기본 발표 차트는 평균 지표 중심으로 먼저 노출한다.

### FR-9. 이벤트 로그 표시

시스템은 benchmark 실행 중 발생한 주요 이벤트를 로그 형태로 보여줘야 한다.

최소 이벤트:

- benchmark queue 등록 또는 시작
- health check 성공/실패
- warmup 시작/완료
- baseline run 시작/완료
- cache run 시작/완료
- reference run 시작/완료
- aggregation 시작/완료
- 오류 발생

`reference run`은 `include_reference=true`일 때만 필요하다.

### FR-9A. 이벤트 스트림 제공

시스템은 UI가 시간축 기반 처리 흐름을 렌더링할 수 있도록 benchmark 실행 이벤트를 순서대로 제공해야 한다.

최소 이벤트 종류:

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

이벤트 스트림 표현 규칙:

- 이벤트 배열 순서는 실제 기록 순서를 보존해야 한다.
- `timestamp`는 run 전체 절대 시각이 아니라 request 내부 상대 경과 ms로 저장해도 된다.
- UI는 배열 순서와 request 내부 상대 시간을 조합해 흐름을 재구성할 수 있어야 한다.
- `ttl_expired`는 TTL 만료를 적극 시뮬레이션하는 시나리오에서 선택적으로 추가할 수 있다.

### FR-10. 결과 시각화

시스템은 아래 결과를 UI에 시각적으로 표시해야 한다.

- `DB Only`, `Redis Hit`, `Redis Miss` 지연시간 비교
- 속도 향상 배수
- 개선율
- 성능 역전 기준 적중률
- 적중률 대비 지연 변화
- 요청 경로 차이 또는 모드별 처리 흐름

### FR-10A. 시간축 기반 흐름 시각화 UI

시스템은 단순 정적 이미지가 아니라, 실제 benchmark 이벤트를 기반으로 한 시간축 시각화 UI를 제공해야 한다.

이 UI는 최소 아래를 만족해야 한다.

- `DB Only`와 `Redis + DB`를 별도 lane으로 구분해 보여준다.
- 요청이 어느 경로를 타는지 흐름 형태로 보여준다.
- `Redis hit`와 `Redis miss -> DB fallback`을 구분해 보여준다.
- 이벤트 배열 순서와 request 상대 시간을 기준으로 공통 playback 축을 구성한다.

### FR-10B. 보조 차트 지원

시스템은 흐름 UI를 보완하기 위해 아래 차트를 함께 지원해야 한다.

- `DB Only`, `Redis Hit`, `Redis Miss` 평균 지연시간 비교 차트

비고:

- 적중률 대비 평균 지연 차트는 보조 설명용으로 유지할 수 있지만, 기본 발표 화면의 첫 그래프는 반드시 `DB Only`, `Redis Hit`, `Redis Miss` 비교를 우선해야 한다.
- p95 비교 차트는 후속 확장 항목으로 두고, 현재 구현에서는 run summary/API에 p95를 유지하되 기본 발표 화면 차트는 평균 중심으로 제공한다.

선택 차트:

- 시간 흐름에 따른 지연시간 변화 차트
- 모드별 요청 경로 비율 차트

### FR-11. 실패 가시성

시스템은 benchmark 실패 시 아래 정보를 표시해야 한다.

- 실패 단계
- 실패 메시지
- 실행 옵션
- 부분 로그

### FR-12. 결과 재조회

시스템은 완료된 benchmark run 결과를 다시 조회할 수 있어야 한다.

### FR-12A. Replay 지원 방식

완료된 run은 저장된 event stream과 result summary를 사용해 다시 설명할 수 있어야 한다.

- 1차 버전에서는 별도 replay API 없이 클라이언트 재생으로 구현해도 된다.
- replay는 같은 run의 이벤트 순서를 반복 설명할 수 있게 해주면 충분하다.

## 8. 비기능 요구사항

### NFR-1. 재현성

같은 입력과 같은 서버/앱 커밋 기준에서는 benchmark 결과를 다시 실행할 수 있어야 한다.

### NFR-2. 가시성

성공과 실패 상태가 UI에서 명확히 구분되어야 한다.

### NFR-2A. 직관성

청중은 시간축 흐름 UI만 보고도 어떤 요청이 왜 빨랐고 왜 느렸는지 이해할 수 있어야 한다.

### NFR-3. 일관성

baseline 경로와 cache 경로는 같은 응답 스키마를 사용해야 한다.

### NFR-4. 로컬 실행 가능성

개발팀은 로컬 환경에서 전체 시스템을 띄우고 테스트할 수 있어야 한다.

### NFR-5. 추적 가능성

모든 benchmark 결과에는 아래 정보가 포함되어야 한다.

- `mini_redis_commit`
- `app_commit`
- 실행 시각
- 실행 옵션

### NFR-6. 단순성

첫 버전은 한 개의 대표 시나리오에 집중해야 하며, 범위 확장은 1차 성공 후 진행한다.

### NFR-7. 경량 백엔드

가능하면 별도 운영 백엔드 없이 구현하고, 필요하더라도 로컬 실행 제어와 결과 조회를 담당하는 얇은 계층만 둬야 한다.

## 9. 제약사항

- 대상 Redis는 `.tmp/mini-redis-dev` 기준 `mini-redis` `dev` 브랜치다.
- 현재 시스템은 인메모리 서버이며 영속성을 제공하지 않는다.
- 발표용 시스템은 `mini-redis` 내부 구현을 수정하지 않는 방향을 우선한다.
- raw RESP 조립을 앱 비즈니스 코드에 직접 넣지 않는다.
- `FLUSHALL` 같은 지원 불명확 명령을 전제로 설계하지 않는다.
- 메인 비교축은 `DB Only`와 `Redis + DB`이며, `Redis Only`는 참고 모드로만 사용한다.

## 10. 데이터 요구사항

### 10-1. Benchmark Run 저장 필드

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

### 10-2. Result Summary 저장 필드

- `db_avg_ms`
- `redis_avg_ms`
- `p95_db_ms`
- `p95_redis_ms`
- `speedup_ratio`
- `improvement_percent`
- `break_even_hit_rate`
- `cache_hit_rate`
- `error_count`

## 11. 완료 기준

이번 단계는 아래 조건을 만족하면 완료로 본다.

- `DB 전용`과 `Redis + DB`를 한 화면에서 비교할 수 있다.
- 시간축 기반 흐름 UI를 통해 두 경로의 차이를 시각적으로 설명할 수 있다.
- 대표 시나리오 1개가 끝까지 실행된다.
- benchmark 시작부터 결과 표시까지 체인이 끊기지 않는다.
- 실패 시 실패 단계와 로그를 확인할 수 있다.
- 결과에 핵심 KPI와 커밋 정보가 남는다.
- 발표자가 같은 조건으로 다시 실행할 수 있다.

## 12. 후속 문서 관계

이 문서를 기준으로 아래 문서를 이어서 관리한다.

- 설계 문서: `docs/benchmark-ui-system-design.md`
- 구현 계획 문서: `docs/implementation-plan.md`
- API 명세 문서: `docs/api-spec.md`
- 테스트 계획 문서: 필요 시 별도 추가

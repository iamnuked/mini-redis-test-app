# mini-redis 벤치마크 UI 및 시스템 구현 계획 문서

## 1. 문서 목적

이 문서는 `docs/requirements.md`와 `docs/benchmark-ui-system-design.md`를 기준으로, 실제 구현을 어떤 순서와 단위로 진행할지 정의한다.

핵심 원칙은 아래와 같다.

- 먼저 돌아가게 만든다.
- 다음으로 재현 가능하게 만든다.
- 마지막에 멋들어진 시각화를 얹는다.

## 2. 구현 전략 요약

구현은 크게 다섯 단계로 나눈다.

1. 실행 환경과 로컬 컨트롤러 구축
2. benchmark 엔진과 데이터 수집 구현
3. 시간축 흐름 UI를 위한 이벤트 모델 연결
4. KPI/차트/흐름 UI 구현
5. 발표용 polish와 replay 모드 보강

첫 버전은 `DB Only`와 `Redis + DB` 비교를 우선하고, `Redis Only`는 참고선으로 마지막에 붙인다.

1차 버전에서 `concurrency`는 설정값과 결과 메타데이터에 포함하지만, 실행 엔진은 순차 실행 기준으로 먼저 고정한다.

## 3. 권장 기술 방향

### 3-1. 백엔드

권장 방향:

- 별도 운영 서버를 만들지 않는다.
- 로컬 실행 제어 계층만 둔다.
- 파일 기반 결과 저장을 우선한다.

최소 역할:

- benchmark 시작
- run 상태 조회
- event stream 조회
- summary 결과 조회
- health check

현재 구현 메모:

- 로컬 HTTP 컨트롤러는 `GET /api/health`, `GET /api/benchmark-runs`, `POST /api/benchmark-runs`, `GET /api/benchmark-runs/:id`, `GET /api/benchmark-runs/:id/events`를 제공한다.
- 프론트 지원용 집계 read model로 `GET /api/benchmark-runs/:id/requests`를 제공한다.
- 발표 화면용 집계 read model로 `GET /api/benchmark-runs/:id/presentation`을 제공한다.
- active run 중복 방지는 지원하지만, 경쟁 상태 없는 완전한 단일 실행 보장은 후속 보강 과제로 둔다.

### 3-2. 프론트엔드

권장 방향:

- KPI/보조 차트는 일반 차트 라이브러리 사용
- 흐름 UI는 SVG 또는 Canvas 커스텀 렌더링

### 3-3. 저장

1차 권장:

- `.tmp/runs/<run_id>.json`
- `.tmp/runs/<run_id>.events.jsonl`

이유:

- 디버깅이 쉽다.
- 재생 모드 구현이 쉽다.
- 별도 DB 없이도 충분하다.

## 4. 단계별 구현 계획

### 단계 1. 실행 환경과 로컬 컨트롤러

목표:

- 로컬에서 benchmark 시스템이 실제로 실행될 수 있게 한다.

작업:

- `mini-redis` health check 구현
- run 생성 API 또는 로컬 runner entrypoint 구현
- `.tmp/runs` 디렉터리 생성
- run id 생성 규칙 정의
- 결과 파일 저장 규칙 정의

산출물:

- `GET /api/health`
- `POST /api/benchmark-runs`
- `GET /api/benchmark-runs/:id`

완료 기준:

- run id가 생성된다.
- health check가 성공/실패를 반환한다.
- 빈 benchmark run 기록을 파일로 남길 수 있다.

### 단계 2. benchmark 엔진 구현

목표:

- 대표 시나리오를 `DB Only`와 `Redis + DB`로 실행할 수 있게 한다.

작업:

- baseline adapter 구현
- MongoDB baseline 설정 파일 정의
- MongoDB seed 스크립트 구현
- `mini-redis` adapter 구현
- scenario runner 구현
- warmup 단계 구현
- cache run 내부 key priming/eviction 규칙 구현
- `DB Only` run 구현
- `Redis + DB` run 구현
- summary metrics 계산

산출물:

- baseline metrics
- cache metrics
- summary JSON

완료 기준:

- 대표 시나리오 1개가 두 경로에서 실행된다.
- 평균 latency, p95, hit rate, speedup을 계산할 수 있다.
- 성능 역전 기준 적중률은 bucket별 평균 latency와 `DB Only` 평균 latency 비교로 계산한다.
- 1차 baseline DB는 로컬 MongoDB를 기본값으로 사용한다.
- 원격 MongoDB Atlas 연결은 후속 검증 옵션으로 분리한다.

### 단계 3. Flow Event Model 구현

목표:

- 시간축 흐름 UI가 소비할 이벤트 스트림을 만든다.

작업:

- request id 생성 규칙 구현
- event_type enum 정의
- stage enum 정의
- request lifecycle 추적
- `.events.jsonl` 저장 구현
- event stream 조회 API 구현
- 프론트 지원용 request timeline read model 구현
- 발표 화면용 presentation read model 구현
- event 배열 순서와 request 상대 시간 기준의 replay 규칙 정의

산출물:

- `GET /api/benchmark-runs/:id/events`
- `GET /api/benchmark-runs/:id/requests`
- `GET /api/benchmark-runs/:id/presentation`
- request 단위 이벤트 목록

완료 기준:

- `request_started`, `cache_lookup_started`, `cache_lookup_completed`, `cache_hit`, `cache_miss`, `db_query_completed`, `cache_set`, `response_sent` 흐름이 이벤트로 남는다.
- run 완료 후 replay 가능한 이벤트 파일이 생긴다.
- `ttl_expired`는 전용 만료 시나리오가 추가될 때까지 선택 이벤트로 둔다.
- 1차 버전의 `after` 조회는 request 상대 `timestamp` 기반 필터이므로, 프론트는 전체 재조회 후 `event_id` dedupe를 우선 사용한다.
- request detail panel은 request timeline read model을 우선 사용하고, 필요한 경우 raw `events[]`를 보조로 사용한다.
- KPI 카드, lane summary, 보조 차트는 presentation read model을 우선 사용하고, raw summary/event 계산은 예외 상황에서만 보조로 사용한다.
- 발표용 첫 화면은 `DB Only`, `Redis Hit`, `Redis Miss` 비교 그래프를 최우선으로 두고, 로그/최근 run/보조 차트는 기본적으로 접거나 숨길 수 있게 구성한다.

### 단계 4. 시각화 UI 구현

목표:

- benchmark 결과를 청중이 바로 이해할 수 있게 보여준다.

작업:

- 헤더/제어 패널 구현
- 첫 비교 그래프 구현
- `DB Only`, `Redis Hit`, `Redis Miss` KPI 카드 구현
- 흐름 lane board 구현
- 보조 차트 구현
- event log panel 구현
- request detail panel 구현

산출물:

- 발표용 단일 페이지 대시보드

완료 기준:

- run 실행부터 결과 표시까지 UI에서 확인 가능하다.
- 첫 그래프만 봐도 `DB Only`, `Redis Hit`, `Redis Miss` 차이를 설명할 수 있다.
- 요청 흐름이 시간축 위에서 보인다.

### 단계 5. polish 및 발표 모드

목표:

- 실제 데모 상황에서 이해하기 쉽고 안정적으로 동작하게 만든다.

작업:

- replay 모드 구현
- playback speed 조절
- lane filter 구현
- `Redis Only` reference 모드 추가
- 오류 메시지 정리
- 시나리오 설명 문구 추가

비고:

- replay는 별도 API보다 저장된 event stream의 클라이언트 재생을 우선한다.
- stop API는 제어 계층이 필요해지기 전까지 1차 범위에서 제외한다.

완료 기준:

- 같은 run을 다시 재생할 수 있다.
- 청중에게 설명하기 쉬운 UI 상태를 제공한다.

## 5. 권장 디렉터리 구조

```text
app/
  api/server.py
  api/contracts.py
  api/timeline.py
  api/presentation.py
  benchmark/models.py
  benchmark/runner.py
  adapters/baseline.py
  adapters/mini_redis.py
  storage/run_store.py
tests/
  test_api_contract.py
  test_request_timeline.py
  test_api_server.py
  test_run_store.py
  test_runner_summary.py
  test_mini_redis_integration.py
  test_sample_run_data.py
docs/
```

비고:

- 위 구조는 현재 구현 기준이다.
- `metrics/`, `flow/`, `ui/`, `scripts/` 분리는 후속 확장 시 선택적으로 도입한다.
- 실제 baseline DB 연결을 위해 `config/` 와 `data/`, `scripts/` 보조 경로를 포함할 수 있다.

## 6. 핵심 모듈 계획

### 6-1. `mini_redis_client`

책임:

- `get`
- `set`
- `delete`
- `expire`
- `ttl`
- health check

주의점:

- 지원 명령 범위를 넘지 않도록 막아야 한다.

### 6-2. `baseline_client`

책임:

- 캐시 없는 기준 응답 생성
- 동일 스키마 반환

### 6-3. `scenario_runner`

책임:

- 시나리오 실행 orchestration
- warmup / baseline / cache 순서 제어
- request id와 event 발행

### 6-4. `metrics_calculator`

책임:

- 평균
- p95
- speedup
- improvement percent
- break-even hit rate

### 6-5. `flow_event_recorder`

책임:

- benchmark lifecycle event 기록
- request lifecycle event 기록
- jsonl 저장

### 6-6. `flow_renderer`

책임:

- event stream을 lane token 모델로 변환
- animation frame 계산
- request detail lookup 제공

### 6-7. `request_timeline_read_model`

책임:

- raw `events[]`를 `request_id` 기준으로 그룹핑
- `path_summary`, `cache_status`, `stage_durations`, `total_duration_ms` 계산
- request detail panel 친화적 응답 생성

### 6-8. `presentation_read_model`

책임:

- KPI 카드용 요약 응답 생성
- lane summary 응답 생성
- 차트용 series 응답 생성
- 프론트가 발표 화면용 계산을 중복 구현하지 않게 지원

## 7. 스프린트 1 작업 목록

스프린트 1의 목표는 "benchmark가 실제로 한 번 돌아가고 결과 JSON이 남는 상태"다.

작업:

- health check
- run create/status API
- baseline client
- mini-redis client
- 대표 시나리오 runner
- summary JSON 저장

스프린트 1 완료 기준:

- UI 없이도 benchmark를 실행할 수 있다.
- 결과 파일을 사람이 열어볼 수 있다.

## 8. 스프린트 2 작업 목록

스프린트 2의 목표는 "흐름 UI에 필요한 이벤트 스트림 확보"다.

작업:

- request lifecycle event 정의
- jsonl event 저장
- event query API
- request timeline read model API
- presentation read model API
- replay 입력 데이터 포맷 고정

스프린트 2 완료 기준:

- 특정 run의 event stream을 다시 읽을 수 있다.
- request path를 이벤트만으로 복원할 수 있다.
- request detail panel과 KPI/차트가 사용할 집계 read model이 준비된다.

## 9. 스프린트 3 작업 목록

스프린트 3의 목표는 "청중에게 보여줄 수 있는 첫 UI"다.

작업:

- benchmark page
- controls
- KPI cards
- lane board
- event log
- request detail panel

스프린트 3 완료 기준:

- benchmark 실행과 결과 시각화가 단일 화면에서 가능하다.

## 10. 스프린트 4 작업 목록

스프린트 4의 목표는 "설명력이 높은 발표 모드"다.

작업:

- replay mode
- playback speed
- lane filter
- reference mode
- copy refinement

스프린트 4 완료 기준:

- 발표자가 같은 run을 반복 설명할 수 있다.

## 11. 테스트 계획

### 11-1. 단위 테스트

- metrics 계산
- break-even 계산
- event 변환
- flow renderer mapping

### 11-2. 통합 테스트

- health check
- `DB Only` benchmark
- `Redis + DB` benchmark
- summary JSON 생성
- events JSONL 생성

### 11-3. UI 테스트

- controls 상태 변경
- run 상태 표시
- lane token 렌더링
- request detail panel 표시

## 12. 리스크와 대응

### 리스크 1. 흐름 UI가 과하게 복잡해짐

대응:

- 첫 버전은 2-lane만 구현
- token 표현을 단순하게 유지

### 리스크 2. 이벤트 수가 너무 많아 렌더링이 버거움

대응:

- 최근 window만 live 렌더
- replay는 축약 재생
- request sampling 추가

### 리스크 3. `mini-redis` 연결 이슈로 데모가 깨짐

대응:

- health check 선행
- baseline only fallback 준비
- 실패 상태 UI를 명확히 제공

### 리스크 4. 수치는 나오는데 청중이 못 알아봄

대응:

- KPI만이 아니라 path visualization을 같이 제공
- request detail panel과 replay 모드 제공

## 13. 현재 시점 권장 다음 작업

지금 바로 착수할 권장 순서는 아래와 같다.

1. `implementation-plan.md` 확정
2. 로컬 run 저장 포맷 결정
3. `mini-redis` health check와 baseline/cache runner 구현
4. Flow Event Model 파일 포맷 확정
5. UI 컴포넌트 골격 생성

# Arena Implementation Reference

## 1. 문서 목적

이 문서는 `mini-redis` 저장소 안에 Arena를 구현하면서 실제로 어떤 판단을 했고, 어떤 파일을 만들거나 수정했고, 현재 어디까지 완료됐는지를 한 번에 정리한 참조 문서다.

이 문서의 목표는 세 가지다.

- 이후 개발자가 현재 구조를 빠르게 이해할 수 있게 한다.
- 이미 구현된 내용과 아직 남아 있는 이슈를 분리해서 기록한다.
- 프론트엔드, gateway, lane, local run 환경을 변경할 때 기준 문서로 삼는다.

## 2. 구현 목표

Arena의 최종 목표는 단순한 데모 페이지가 아니라, `mini-redis`를 실제 캐시 엔진으로 사용하면서 아래 두 경로를 같은 입력으로 비교하는 실험 환경을 제공하는 것이다.

- `redis + db`
- `db only`

이 비교는 단순한 응답 결과 비교가 아니라 다음을 함께 보여주도록 설계했다.

- 처리 경로 차이
- Redis cache hit/miss
- Mongo read 수 차이
- lane 내부 처리 시간 차이
- 시나리오별 동작 변화

## 3. 구현 과정 요약

### 3-1. 초기 상태와 한계

초기 Arena는 gateway 프로세스 내부에서 두 lane 어댑터를 직접 실행하는 형태에 가까웠다.

- `redis_db`와 `db_only`가 같은 프로세스 안에서 실행됐다.
- DB는 실제 MongoDB가 아니라 프로세스 내부 `dict` 기반 `InMemoryMongoRepository`였다.
- 이 구조는 처리 경로를 보여주는 데는 충분했지만, 속도 비교용 구조로는 부적절했다.

문제가 된 이유:

- 같은 gateway 안에서 lane 실행 순서와 이벤트 루프 스케줄링 영향을 받는다.
- `db_only`가 실제 Mongo가 아니라 RAM `dict` 조회라서 지나치게 유리해질 수 있다.
- Redis TCP 호출 비용과 메모리 딕셔너리 조회를 비교하게 되어 benchmark 의미가 약해진다.

### 3-1-1. 저장소 정리 방향

초기에는 `mini-redis-test-app`에 Arena 프로토타입과 협업 문서가 함께 존재했다. 현재 구현은 `mini-redis` 안으로 흡수됐고, 활성 기준은 `mini-redis` 하나로 본다.

정리 원칙:

- 실행 코드와 테스트는 `mini-redis`를 기준으로 유지한다.
- `mini-redis-test-app`은 과거 프로토타입/참고본으로만 취급한다.
- 협업 규칙, 업무분장, 작업 ID 같은 문서는 활성 개발 기준에서 제외한다.

### 3-2. 재설계 방향 확정

이후 설계 방향은 `docs/arena/benchmark-architecture.md`에 정리된 기준으로 고정했다.

핵심 원칙:

- gateway는 fan-out과 집계만 담당
- lane-a는 `redis + mongo`
- lane-b는 `mongo only`
- Redis는 `mini-redis` 서버와 RESP/TCP로 통신
- DB는 실제 MongoDB 사용
- 속도 비교 기준은 gateway RTT가 아니라 lane 내부 `service_time_ms`

### 3-3. 멀티 서비스 구조로 분리

아래 구조를 기준으로 서비스를 분리했다.

```text
browser
  -> gateway :8200

gateway
  -> lane-a :8201
  -> lane-b :8202

lane-a
  -> mini-redis :6380
  -> mongo-a :27018

lane-b
  -> mongo-b :27019
```

이 단계에서 다음이 구현됐다.

- gateway용 엔트리포인트 추가
- lane-a 서비스 추가
- lane-b 서비스 추가
- gateway 내부 어댑터 직접 호출 제거
- HTTP lane client 도입

### 3-4. 실제 Mongo 경계 추가

기존 인메모리 저장소는 완전히 제거하지 않고, 아래 두 모드를 동시에 유지했다.

- `InMemoryMongoRepository`
- `PyMongoArenaRepository`

의도:

- 테스트와 빠른 smoke test는 인메모리 모드로 계속 돌릴 수 있게 유지
- 실제 속도 비교와 로컬 실행은 `pymongo` 모드로 분리

### 3-5. 로컬 실행 자동화

Docker 없는 환경에서도 전체 Arena를 재현할 수 있도록 로컬 실행 스크립트를 추가했다.

- Mongo 2개
- `mini-redis`
- lane-a
- lane-b
- gateway

Mongo 데이터 디렉터리는 저장소 내부 `.local/arena/*` 아래에 두도록 고정했다.

### 3-6. 프론트엔드 재구성

프론트는 초기의 설명형/데모형 레이아웃에서, 한 화면 고정형 모니터링 UI로 재구성했다.

요구사항 반영 내용:

- 거창한 hero/title 제거
- 한 페이지 안에서 스크롤 없는 레이아웃
- 상단은 좌우 lane 비교
- 하단은 `Status`, `Manual Command`, `Input Scenarios`
- 6개 동적 패널은 내부 스크롤 허용
- `redis_db`와 `db_only`를 같은 요소로 나란히 비교
- 다크 톤 UI로 통일
- 동적 패널은 CLI 로그처럼 한 줄 단위로 흐르게 구성

## 4. 현재 아키텍처

### 4-1. 서비스 구성

- `gateway`
  - 브라우저와 HTTP/SSE 통신
  - manual command 수신
  - scenario orchestration
  - lane-a/b fan-out
  - summary 생성
  - events broadcast

- `lane-a`
  - Redis + Mongo 처리
  - cache hit/miss 계산
  - Redis set/get/del/expire 수행
  - lane 내부 timing 측정

- `lane-b`
  - Mongo only 처리
  - lane 내부 timing 측정

- `mini-redis`
  - 실제 Redis-compatible cache engine

- `mongo-a`, `mongo-b`
  - lane별 독립 저장소

### 4-2. 통신 방식

- Browser <-> Gateway: HTTP + SSE
- Gateway <-> Lane A/B: HTTP JSON
- Lane A <-> mini-redis: Redis RESP/TCP
- Lane A/B <-> MongoDB: Mongo driver/TCP

중요:

- Redis를 쓰는 경로는 HTTP가 아니다.
- 브라우저는 Redis와 직접 통신하지 않는다.
- gateway는 lane 로직을 직접 실행하지 않는다.

### 4-3. 측정 기준

속도 비교 기준은 lane 내부에서 측정한 값이다.

- `service_time_ms`
- `db_time_ms`
- `redis_time_ms`
- `gateway_round_trip_ms`
- `mongo_reads`
- `cache.hit`
- `cache.miss`

이 중 실제 비교에 가장 중요한 값은 `service_time_ms`다.

## 5. 현재 프론트엔드 상태

현재 대시보드는 `web/arena_dashboard` 아래에서 제공된다.

레이아웃:

- 상단 왼쪽: `mini-redis + MongoDB`
- 상단 오른쪽: `MongoDB Only`
- 하단 왼쪽: `Status`
- 하단 가운데: `Manual Command`
- 하단 오른쪽: `Input Scenarios`

상단 lane별 4패널 구성:

- `Mongo Read History`
- `Latency History`
- `Monitoring`
- `Answer`

세부 정책:

- 페이지 전체는 `100vh`
- 전체 페이지 스크롤 없음
- 6개 동적 패널만 내부 스크롤 허용
- 동적 패널은 CLI 로그처럼 한 줄씩 출력
- 시간은 `HH:MM`
- `Monitoring`과 `Status`는 표 형태로 압축

프론트에서 표시하는 대표 정보:

- latest lane 상태
- 최근 latency 로그
- 최근 mongo read 로그
- 최근 answer 로그
- gateway/lane/mongo/redis/SSE health
- manual command 입력
- scenario 실행과 reset

## 6. 현재 지원 기능

### 6-1. Manual Command

지원 명령:

- `SET`
- `GET`
- `DEL`

입력값:

- `Command`
- `Key`
- `TTL enabled for Redis lane`
- `Value`

동작:

- gateway가 같은 요청을 두 lane에 fan-out
- 각 lane 결과를 개별 패널에 표시
- summary와 health 상태를 갱신
- SSE로 history와 answer 패널에 반영

### 6-2. Scenarios

현재 제공 시나리오:

- `Hot Key`
- `TTL Expiry`

입력값:

- `Users`
- `Duration`
- `TTL`

동작:

- gateway가 scenario task를 시작
- 각 step의 결과를 event로 브로드캐스트
- history/answer 패널이 지속 갱신
- reset 시 task 취소 및 key 정리

### 6-3. Status / Monitoring

현재 health 계층:

- overall
- SSE
- gateway
- mini-redis
- lane-a
- mongo-a
- lane-b
- mongo-b

추가 상태:

- tracked keys
- retained events
- current scenario
- last health poll
- last request
- last event

## 7. 현재까지 생성/편집한 주요 파일

아래 목록은 Arena 구현 과정에서 실제로 생성하거나, Arena 목적 때문에 수정한 핵심 파일을 영역별로 정리한 것이다.

### 7-1. 문서

- `docs/arena/README.md`
- `docs/arena/final-direction.md`
- `docs/arena/mini-redis-integration.md`
- `docs/arena/benchmark-architecture.md`
- `docs/arena/local-mongo-runbook.md`
- `docs/arena/implementation-reference.md`

### 7-2. 엔트리포인트

- `cmd/arena_gateway/main.py`
- `cmd/arena_lane_a/main.py`
- `cmd/arena_lane_b/main.py`
- `cmd/mini_redis_server/main.py`

### 7-3. Gateway

- `internal/arena/api/app.py`
- `internal/arena/api/manual_command_api.py`
- `internal/arena/api/scenario_api.py`
- `internal/arena/api/events_api.py`
- `internal/arena/api/health_api.py`
- `internal/arena/gateway/service.py`
- `internal/arena/gateway/lane_client.py`
- `internal/arena/gateway/result_normalizer.py`
- `internal/arena/gateway/models.py`

### 7-4. Lane 공통/핵심 로직

- `internal/arena/common/models.py`
- `internal/arena/lane/redis_db_adapter.py`
- `internal/arena/lane/db_only_adapter.py`
- `internal/arena/lane/redis_client.py`
- `internal/arena/lane/cache_policy.py`

### 7-5. Lane 서비스

- `internal/arena/lane_a/api/app.py`
- `internal/arena/lane_a/api/routes.py`
- `internal/arena/lane_b/api/app.py`
- `internal/arena/lane_b/api/routes.py`

### 7-6. Mongo / Event / Scenario

- `internal/arena/mongo/repository.py`
- `internal/arena/events/bus.py`
- `internal/arena/events/history.py`
- `internal/arena/scenario/models.py`
- `internal/arena/scenario/hot_key.py`
- `internal/arena/scenario/ttl_expiry.py`
- `internal/arena/scenario/reset.py`
- `internal/arena/scenario/runner.py`

### 7-7. 프론트엔드

- `web/arena_dashboard/index.html`
- `web/arena_dashboard/app.js`
- `web/arena_dashboard/styles.css`

### 7-8. 테스트

- `tests/arena/test_gateway_contracts.py`
- `tests/arena/test_gateway_http_client.py`
- `tests/arena/test_lane_apps.py`
- `tests/arena/test_redis_db_adapter.py`
- `tests/arena/test_redis_client.py`

### 7-9. 실행/배포

- `scripts/arena-local-common.sh`
- `scripts/arena-local-up.sh`
- `scripts/arena-local-down.sh`
- `scripts/arena-local-status.sh`
- `deploy/docker-compose.arena.yml`
- `Dockerfile`

### 7-10. 저장소 공용 파일 수정

- `README.md`
- `requirements.txt`
- `.gitignore`
- `pytest.ini`

## 8. 중요한 구현 결정

### 8-1. 인메모리 저장소를 완전히 지우지 않은 이유

인메모리 구현은 benchmark 기준으로는 부정확하지만, 아래 두 이유 때문에 유지했다.

- 테스트를 빠르게 실행하기 쉽다.
- Mongo 없는 환경에서도 기능 smoke test가 가능하다.

다만 실제 속도 비교 기준은 항상 `pymongo` 모드다.

### 8-2. Redis는 별도 프로토콜을 유지

Redis 경로는 HTTP로 흉내 내지 않고, `redis-py`를 통해 `mini-redis`와 TCP로 직접 통신하게 유지했다. 이 판단은 Arena의 핵심 목적과 직접 연결된다. 그래야 `mini-redis`를 실제 캐시 엔진으로 쓴다고 말할 수 있다.

### 8-3. Mongo는 lane별로 분리

strict benchmark에 가까운 비교를 위해 lane별 Mongo를 분리했다.

- `mongo-a`
- `mongo-b`

로컬 실행에서는 서로 다른 포트와 서로 다른 dbpath를 사용한다.

### 8-4. 프론트는 설명보다 관측 우선

사용자가 요구한 방향에 따라 프론트는 더 이상 설명 페이지가 아니라, compact monitoring dashboard를 우선하도록 정리했다.

## 9. 현재 검증 상태

### 9-1. 테스트

현재 Arena 테스트는 다음 명령으로 검증했다.

```bash
PYTHONPATH=. .venv311/bin/pytest -q tests/arena
```

최근 기준 결과:

- `8 passed`

### 9-2. 정적 검증

프론트 JS 문법 검증:

```bash
node --check web/arena_dashboard/app.js
```

### 9-3. 로컬 실행 검증

로컬 전체 기동:

```bash
./scripts/arena-local-up.sh
./scripts/arena-local-status.sh
```

확인 대상:

- gateway health
- lane-a health
- lane-b health
- Redis path 동작
- Mongo 분리 저장
- Manual command 동작
- Scenario 실행

## 10. 현재 알려진 이슈와 한계

### 10-1. 같은 머신 비교의 한계

현재는 모든 서비스를 같은 머신에서 띄우기 때문에 절대 성능 수치는 환경 영향을 크게 받는다. 따라서 현재 Arena는 다음 두 가지를 모두 제공하지만, 해석은 구분해서 해야 한다.

- 구조 비교
- 상대적인 lane timing 비교

strict benchmark 수준의 결과를 원하면 lane별 자원 분리나 컨테이너/호스트 분리가 추가로 필요하다.

### 10-2. 프론트는 계속 미세조정 대상

현재 프론트는 요구사항에 맞춰 크게 재구성됐지만, 실제 브라우저 해상도에 따라 다음이 다시 조정될 수 있다.

- 패널 내 텍스트 밀도
- 표 행 수
- 로그 컬럼 폭
- 모바일 또는 저해상도 대응

### 10-3. Docker 경로는 문서화됐지만 로컬 `mongod` 경로가 더 확실하다

`deploy/docker-compose.arena.yml`은 준비되어 있다. 다만 실제 개발 과정에서는 로컬 `mongod` 기반 검증을 먼저 확정했다. 이유는 작업 환경에 Docker가 항상 있는 것이 아니었기 때문이다.

### 10-4. CSS 정리 여지

프론트가 여러 차례 레이아웃 변경을 거치면서 사용하지 않는 보조 스타일이 일부 남아 있을 가능성이 있다. 동작에는 문제가 없지만, 추후 스타일 정리 리팩터링 여지는 있다.

## 11. 다음 개발자가 먼저 읽어야 할 파일

우선순위 순서:

1. `docs/arena/implementation-reference.md`
2. `docs/arena/benchmark-architecture.md`
3. `docs/arena/local-mongo-runbook.md`
4. `internal/arena/common/models.py`
5. `internal/arena/gateway/service.py`
6. `internal/arena/lane/redis_db_adapter.py`
7. `internal/arena/lane/db_only_adapter.py`
8. `web/arena_dashboard/index.html`
9. `web/arena_dashboard/app.js`
10. `web/arena_dashboard/styles.css`

## 12. 다음 작업 권장 순서

### 12-1. 기능 측면

- benchmark 전용 view와 trace view를 더 명확히 분리할지 판단
- scenario 종류 추가
- scenario별 누적 통계 저장 방식 강화
- reset/seed 가시성 강화

### 12-2. 운영 측면

- 로컬 benchmark 자동 실행 스크립트 추가
- Docker 경로 최종 검증
- health 상세 지표 확장

### 12-3. 프론트 측면

- 해상도별 미세조정
- log 패널 검색/필터 여부 검토
- panel density 추가 튜닝

## 13. 결론

현재 Arena는 단순한 학습용 mock 단계는 벗어났다.

이미 구현된 것:

- multi-service 구조
- Redis 실제 연동
- Mongo 실제 연동 경계
- local run automation
- one-page monitoring dashboard
- manual/scenario 비교
- test suite

아직 계속 다듬어야 하는 것:

- strict benchmark 정확도 강화
- Docker 경로 최종 운영 검증
- 프론트 미세조정

앞으로 Arena를 확장할 때는 이 문서를 기준으로, "학습용 시각화"와 "속도 비교 시스템"을 섞지 말고 분리해서 판단하는 것이 중요하다.

# redis-py 호환성 계획 문서

## 1. 문서 목적

이 문서는 현재 `mini-redis`가 `redis-py`와 완전히 호환되지 않는 이유를 정리하고, 호환성을 확보하기 위한 단계별 구현 계획을 정의한다.

이 문서는 기존 기준 문서를 대체하지 않는다.

- 현재 제품 범위와 구조의 기준: `architecture.md`, `api-spec.md`, `requirements.md`
- 본 문서의 역할: `redis-py` 호환성 확장을 위한 별도 계획 문서

## 2. 현재 상태 요약

현재 `mini-redis`는 다음을 지원한다.

- RESP3 기반 명령 처리
- `HELLO 3` 협상
- `String`, `Hash`, `List`, `Set`, `Sorted Set`
- CLI 단일 명령 실행 및 REPL
- TTL 지연 삭제 및 백그라운드 sweeper

현재 구조는 학습용 mini-redis로서는 충분하지만, 일반적인 Python 애플리케이션에서 사용하는 `redis-py` 클라이언트와는 연결 모델과 초기 핸드셰이크 방식에서 차이가 있다.

## 3. 현재 비호환 원인

### 3-1. 연결당 요청 1회 처리 구조

현재 서버 세션 처리는 사실상 요청 1회 처리 후 종료되는 방식에 가깝다.

`redis-py`는 보통 하나의 TCP 연결을 재사용하며, 같은 연결에서 여러 명령을 연속으로 전송한다.

따라서 현재 구조는 다음 상황에서 바로 충돌한다.

- 같은 연결에서 연속 명령 실행
- 연결 풀 재사용
- health check
- 초기 핸드셰이크 후 일반 명령 전송

### 3-2. 연결 상태 관리 부재

현재 구현은 `HELLO 3` 즉시 응답은 처리할 수 있지만, 연결별 프로토콜 상태를 유지하지 않는다.

`redis-py` 호환을 위해서는 연결 단위로 최소한 다음 상태를 관리해야 한다.

- 현재 RESP 버전
- 선택된 DB
- 인증 여부
- client name / client metadata

### 3-3. redis-py 초기 명령 미지원 또는 부분 지원

`redis-py`는 연결 시점에 환경에 따라 다음 명령을 전송할 수 있다.

- `HELLO 2` 또는 `HELLO 3`
- `AUTH`
- `CLIENT SETNAME`
- `CLIENT SETINFO`
- `SELECT`
- `PING`

현재 `mini-redis`는 이 중 일부만 직접 지원하거나, 연결 상태와 결합된 방식으로는 지원하지 않는다.

### 3-4. RESP2 기본 가정과의 차이

`redis-py`는 기본적으로 RESP2를 사용하고, 명시적으로 `protocol=3`을 줄 때 RESP3를 사용한다.

반면 현재 `mini-redis`는 사실상 RESP3 중심으로 설계되어 있다.

즉, `redis-py` 기본 설정과 바로 호환되려면 RESP2 기본 연결도 받아들일 수 있어야 한다.

## 4. 목표 호환 수준

본 계획의 목표는 `redis-py` 전체 기능을 구현하는 것이 아니라, 일반적인 앱 서버 사용 시나리오에서 문제없이 사용할 수 있는 수준의 호환성을 확보하는 것이다.

1차 목표:

- `redis.Redis(host=..., port=...)`로 연결 가능
- 같은 연결에서 여러 명령 연속 실행 가능
- `PING` 동작 가능
- `SELECT 0` 동작 가능
- `CLIENT SETNAME`과 `CLIENT SETINFO`를 최소한 오류 없이 처리
- `SET`, `GET`, `DEL`, `EXPIRE`, `TTL` 및 현재 지원 자료구조 명령 사용 가능

2차 목표:

- `protocol=3` 설정 사용 가능
- RESP2 / RESP3 전환 지원
- `decode_responses=True` 동작 검증
- health check / reconnect 시나리오 검증

비목표:

- Redis 전체 명령 완전 호환
- Pub/Sub
- Streams
- Transactions
- Lua scripting
- Cluster / Sentinel

## 5. 권장 해결 방향

가장 바람직한 방향은 앱 서버 쪽에 커스텀 클라이언트를 두는 것이 아니라, `mini-redis` 서버가 `redis-py`가 기대하는 서버 동작을 제공하도록 바꾸는 것이다.

핵심 방향은 다음 세 가지다.

1. 세션을 지속 연결 구조로 변경
2. 연결별 상태 관리 도입
3. `redis-py`가 기대하는 최소 연결 명령 지원

## 6. 설계 변경 계획

### 6-1. SessionHandler를 다중 명령 세션으로 변경

현재:

- `recv()` 1회
- 요청 1회 처리
- 응답 1회 전송

목표:

- 연결이 종료될 때까지 반복
- 프레임을 순차적으로 읽음
- 명령마다 응답 전송
- 클라이언트 종료 또는 치명적 프로토콜 오류 시 세션 종료

예상 영향 파일:

- `internal/server/session_handler.py`
- 필요 시 `internal/server/server.py`

### 6-2. 연결 상태 모델 도입

연결별 컨텍스트를 도입한다.

예상 상태:

- `protocol_version`
- `selected_db`
- `client_name`
- `authenticated`

예상 파일:

- 신규: `internal/server/session_context.py`
- 수정: `internal/server/session_handler.py`
- 필요 시 `internal/protocol/resp/protocol_handler.py`

### 6-3. RESP2 기본, RESP3 선택 전환

`redis-py` 기본 동작에 맞추기 위해 기본 프로토콜은 RESP2로 두고, `HELLO 3` 수신 시 RESP3로 전환하는 방식을 권장한다.

이 경우 다음이 가능해진다.

- 기본 `redis.Redis(...)` 호환성 개선
- `redis.Redis(protocol=3)` 호환성 제공

예상 파일:

- `internal/protocol/resp/request_decoder.py`
- `internal/protocol/resp/response_encoder.py`
- `internal/protocol/resp/protocol_handler.py`

### 6-4. 최소 연결 명령 지원

우선순위 순으로 지원한다.

필수:

- `PING`
- `SELECT`
- `HELLO`

사실상 필요:

- `CLIENT SETNAME`
- `CLIENT SETINFO`

정책:

- `CLIENT SETNAME`은 상태 저장 후 `OK`
- `CLIENT SETINFO`는 초기에는 no-op로 `OK` 반환 가능
- `SELECT`는 우선 `0`만 허용하거나, 필요 시 다중 DB 미지원 오류 정책을 정의

예상 파일:

- `internal/command/validator.py`
- `internal/service/command_service.py`
- 필요 시 `internal/protocol/resp/messages.py`

### 6-5. AUTH 정책 정리

현재 프로젝트가 인증을 지원하지 않는다면, 초기 단계에서는 명시적으로 다음 중 하나를 선택해야 한다.

1. 인증 미지원, `AUTH`에 명확한 에러 반환
2. 인증 비활성 모드에서는 `AUTH` no-op 허용

앱 서버 호환성만 고려하면 2번이 더 편리할 수 있지만, 의미상 혼동이 있으므로 문서 정책을 먼저 정한 뒤 구현하는 것이 좋다.

## 7. 단계별 구현 로드맵

### 단계 1. 세션 지속 연결화

목표:

- 한 연결에서 여러 명령 처리 가능

작업:

- `SessionHandler` 루프화
- EOF 처리
- 프로토콜 오류와 세션 종료 규칙 정리

완료 기준:

- 같은 TCP 연결에서 `PING`, `SET`, `GET` 연속 수행 가능

### 단계 2. 연결 상태와 핸드셰이크 명령

목표:

- `HELLO`, `SELECT`, `CLIENT SETNAME`, `CLIENT SETINFO` 지원

작업:

- session context 추가
- 연결별 protocol version 관리
- 최소 client metadata 처리

완료 기준:

- `redis-py` 연결 초기화 명령이 오류 없이 통과

### 단계 3. RESP2/RESP3 겸용화

목표:

- 기본 연결과 `protocol=3` 연결 모두 지원

작업:

- RESP2 요청 파싱
- RESP2 응답 인코딩
- `HELLO` 이후 버전 전환

완료 기준:

- `redis.Redis(...)`
- `redis.Redis(protocol=3)`
둘 다 연결 가능

### 단계 4. 호환성 테스트 강화

목표:

- 실제 `redis-py` 클라이언트로 end-to-end 검증

작업:

- 연결 테스트
- health check 테스트
- decode_responses 테스트
- reconnect / pool 시나리오 테스트

완료 기준:

- 앱 서버 예제 코드로 실제 CRUD 수행 가능

## 8. 테스트 계획

### 8-1. 단위 테스트

- 세션 상태 전이
- `HELLO` 버전 전환
- `PING`, `SELECT`, `CLIENT SETNAME`, `CLIENT SETINFO`
- RESP2/RESP3 인코딩/디코딩 분기

### 8-2. 통합 테스트

- 같은 연결에서 여러 명령 실행
- 연결 종료 시 상태 정리
- health check 요청 처리

### 8-3. redis-py 실제 호환 테스트

별도 테스트 파일 예시:

- `tests/test_redis_py_compatibility.py`

검증 항목:

- `redis.Redis(...).ping()`
- `set/get`
- 자료구조 명령 일부
- `protocol=3`
- `decode_responses=True`

## 9. 위험 요소

### 9-1. 세션 구조 변경 영향

`SessionHandler`를 루프 기반으로 바꾸면 현재 timeout, shutdown, metrics 처리 방식이 영향을 받는다.

따라서 다음을 함께 점검해야 한다.

- idle timeout
- graceful shutdown
- connection count metrics
- request metrics

### 9-2. RESP2/RESP3 동시 지원 복잡도

RESP2와 RESP3를 동시에 지원하면 decoder, encoder, 타입 매핑, 테스트 복잡도가 증가한다.

따라서 기본 목표를 `redis-py` 앱 서버 사용에 필요한 최소 범위로 제한하는 것이 중요하다.

### 9-3. AUTH 정책 혼선

인증을 실제로 지원하지 않으면서 `AUTH`를 no-op 처리하면 오해가 생길 수 있다.

이 부분은 문서 정책과 테스트를 반드시 함께 관리해야 한다.

## 10. 권장 우선순위

가장 먼저 할 일:

1. `SessionHandler` 지속 연결 구조화
2. `PING`, `SELECT`, `CLIENT SETNAME`, `CLIENT SETINFO` 최소 지원
3. redis-py 실제 연결 smoke test 추가

이후 할 일:

4. RESP2 기본 지원
5. RESP3 전환 정교화
6. health check / reconnect / pool 호환성 강화

## 11. 결론

`redis-py` 호환성 문제의 핵심은 단순 명령 부족보다도 연결 모델 차이에 있다.

따라서 가장 올바른 해결 방향은:

- 세션 지속 연결 지원
- 연결 상태 관리
- 최소 연결 핸드셰이크 명령 지원
- RESP2/RESP3 겸용화

순으로 서버 자체를 확장하는 것이다.

이는 앱 서버 쪽에 별도 우회 로직을 넣는 것보다 장기적으로 더 안정적이고, 실제 Redis 사용 방식에도 더 가깝다.

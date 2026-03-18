# 미니 Redis 4인 개발 업무 분장 문서

## 1. 문서 목적

이 문서는 현재 미니 Redis 문서와 파이썬 코드 구조를 기준으로, 4명이 병렬로 작업할 때 충돌을 줄이기 위한 역할 분장 기준을 정의한다.

본 문서는 [`architecture.md`](architecture.md), [`api-spec.md`](api-spec.md), [`implementation-plan.md`](implementation-plan.md)를 기반으로 하며, 파일 소유권과 협업 경계를 명확히 하는 것을 목적으로 한다.

## 2. 분장 원칙

- 한 사람은 가능한 한 하나의 계층 또는 인접한 계층만 담당한다.
- 같은 파일을 여러 사람이 동시에 수정하지 않도록 파일 소유권을 명확히 둔다.
- 공통 규약 파일은 사전에 인터페이스를 합의한 뒤 한 사람이 대표로 수정한다.
- 병렬 작업은 `인터페이스 합의 -> 각자 구현 -> 통합 테스트` 순서로 진행한다.
- 비즈니스 로직, 프로토콜 처리, 서버 처리, CLI 처리를 분리한다.

## 3. 전체 역할 요약

### 담당자 1. 프로토콜 및 명령 해석

역할:

- RESP3 프레임 처리
- 명령 파싱 및 검증
- `HELLO 3` 협상 처리

소유 파일:

- `internal/protocol/resp/types.py`
- `internal/protocol/resp/request_decoder.py`
- `internal/protocol/resp/response_encoder.py`
- `internal/protocol/resp/messages.py`
- `internal/protocol/resp/hello_handler.py`
- `internal/command/command.py`
- `internal/command/parser.py`
- `internal/command/validator.py`
- `internal/command/errors.py`

완료 기준:

- RESP3 요청을 내부 명령 모델로 변환할 수 있다.
- `HELLO 3` 협상을 처리할 수 있다.
- 지원 명령의 인자 수와 타입 검증이 가능하다.
- 오류 요청에 대해 일관된 프로토콜 에러 모델을 반환할 수 있다.

### 담당자 2. 저장소, TTL, 서비스 로직

역할:

- 인메모리 저장소 구현
- TTL 계산 및 만료 처리
- `SET`, `GET`, `DEL`, `EXPIRE`, `TTL` 서비스 로직 구현

소유 파일:

- `internal/repository/store_repository.py`
- `internal/repository/ttl_repository.py`
- `internal/repository/in_memory_store.py`
- `internal/repository/in_memory_ttl.py`
- `internal/expiration/expiration_manager.py`
- `internal/expiration/ttl_calculator.py`
- `internal/expiration/expiration_sweeper.py`
- `internal/service/set_service.py`
- `internal/service/get_service.py`
- `internal/service/del_service.py`
- `internal/service/expire_service.py`
- `internal/service/ttl_service.py`

공동 조정 파일:

- `internal/service/command_service.py`

완료 기준:

- 값 저장소와 TTL 저장소가 동작한다.
- 지연 삭제와 주기적 정리의 기본 로직이 동작한다.
- 필수 5개 명령의 서비스 결과가 요구사항과 일치한다.
- `command_service.py`에서 명령 분기 연결이 완료된다.

### 담당자 3. 서버, 자원 보호, 관측

역할:

- TCP 서버 실행
- 세션 단위 요청/응답 처리
- 연결 제한 및 요청 크기 제한
- 로그와 메트릭 기본 구조 구현

소유 파일:

- `internal/server/server.py`
- `internal/server/session_handler.py`
- `internal/server/shutdown.py`
- `internal/guard/resource_guard.py`
- `internal/guard/limits.py`
- `internal/observability/logger.py`
- `internal/observability/metrics.py`
- `cmd/mini_redis_server/main.py`

공동 조정 파일:

- `internal/server/session_handler.py`

설명:

- `session_handler.py`는 담당자 1의 프로토콜 계층, 담당자 2의 서비스 계층과 맞물리므로 최종 조립은 담당자 3이 맡되, 입력과 출력 인터페이스는 사전 합의가 필요하다.

완료 기준:

- 서버가 지정 포트에서 연결을 수락할 수 있다.
- 요청 단위 오류가 전체 서버 중단으로 이어지지 않는다.
- 자원 제한 정책이 세션 처리 경로에 연결된다.
- 기본 로그와 메트릭 수집 지점이 들어간다.

### 담당자 4. CLI, 설정, 테스트 및 통합

역할:

- CLI 구현
- 설정 로딩
- 테스트 뼈대 작성
- 통합 검증과 수용 기준 점검

소유 파일:

- `cmd/mini_redis_cli/main.py`
- `internal/config/runtime_config.py`
- `internal/config/defaults.py`
- `internal/clock/clock.py`
- `internal/clock/system_clock.py`
- `internal/clock/fake_clock.py`
- `tests/test_imports.py`
- 향후 추가될 `tests/test_*.py` 파일 전반

공동 조정 파일:

- `cmd/mini_redis_cli/main.py`

설명:

- CLI는 담당자 1의 RESP3 인코딩/디코딩 방식, 담당자 3의 서버 접속 흐름과 맞물리므로 출력 형식과 종료 코드 정책을 미리 합의해야 한다.

완료 기준:

- CLI가 `HELLO 3`을 먼저 보내고 단일 명령을 실행할 수 있다.
- 성공/실패 출력과 종료 코드가 문서와 일치한다.
- 단위 테스트와 통합 테스트의 기본 골격이 준비된다.
- 수용 기준을 검증하는 테스트 시나리오를 정리한다.

## 4. 공통 협업 규칙

### 4-1. 사전 합의가 필요한 인터페이스

다음 항목은 각 담당자가 구현 전에 먼저 합의해야 한다.

- 내부 명령 모델의 형태
- 서비스 계층의 반환 타입
- RESP3 오류 모델과 오류 메시지 상수
- 세션 핸들러가 호출할 서비스 진입점 시그니처
- CLI가 사용할 응답 렌더링 규칙
- 설정 객체 구조와 기본값 공급 방식

### 4-2. 동시 수정 금지 파일

다음 파일은 한 시점에 한 사람만 수정하는 것을 원칙으로 한다.

- `internal/service/command_service.py`
- `internal/server/session_handler.py`
- `cmd/mini_redis_cli/main.py`
- `cmd/mini_redis_server/main.py`
- `internal/config/runtime_config.py`

### 4-3. 병합 순서 권장

병렬 작업은 다음 순서로 병합하는 것이 좋다.

1. 담당자 1이 RESP3 및 명령 인터페이스를 먼저 고정한다.
2. 담당자 2가 저장소와 서비스 로직을 구현한다.
3. 담당자 3이 서버와 세션 처리에 담당자 1, 2의 결과를 연결한다.
4. 담당자 4가 CLI와 테스트를 연결하고 전체 흐름을 검증한다.

## 5. 단계별 병렬 작업 전략

### 단계 1. 기반 합의

참여자:

- 전원

합의 항목:

- 내부 명령 모델
- 서비스 반환 모델
- 에러 상수
- 설정 객체 구조

결과물:

- 인터페이스 문서 또는 간단한 코드 스텁 확정

### 단계 2. 독립 구현

병렬 가능 작업:

- 담당자 1: RESP3 디코딩/인코딩, 파서, 검증기
- 담당자 2: 저장소, TTL, 서비스
- 담당자 3: 서버, 세션, guard, observability
- 담당자 4: CLI, 설정, 테스트 골격

설명:

- 이 단계에서는 공동 조정 파일 수정을 최소화한다.
- 각자 자기 소유 파일 중심으로만 작업한다.

### 단계 3. 조립 및 통합

주요 통합 지점:

- `internal/service/command_service.py`
- `internal/server/session_handler.py`
- `cmd/mini_redis_cli/main.py`

설명:

- 이 단계에서는 담당자 3과 담당자 4가 중심이 되어 전체 경로를 연결한다.
- 담당자 1과 담당자 2는 인터페이스 불일치 수정에 집중한다.

## 6. 권장 세부 분장

### 담당자 1 상세 작업

- RESP3 Array 파싱
- Blob String, Number, Null 처리
- `HELLO 3` 요청/응답 모델 구현
- 명령어 정규화
- 명령어 인자 검증
- 프로토콜 오류 메시지 상수 정리

### 담당자 2 상세 작업

- 값 저장소 CRUD
- TTL 저장소 CRUD
- `list_keys()` 기반 sweeper 지원
- `ExpirationManager` 구현
- `ExpirationSweeper` 구현
- `SET`, `GET`, `DEL`, `EXPIRE`, `TTL` 서비스 구현

### 담당자 3 상세 작업

- 서버 시작/종료 루프
- 세션별 요청 수신과 응답 전송
- 요청 크기 제한
- 연결 수 제한
- graceful shutdown 연결
- 기본 로그와 메트릭 기록 지점 연결

### 담당자 4 상세 작업

- CLI 인자 파싱
- `HELLO 3` 송신
- 명령 프레임 생성
- 응답 표시와 종료 코드 처리
- 테스트 공통 fixture 설계
- 단위/통합 테스트 추가

## 7. 위험 파일과 대응 방법

### 7-1. `internal/server/session_handler.py`

위험:

- 프로토콜, 서비스, observability가 모두 만나는 조립 지점이다.

대응:

- 담당자 3이 최종 소유한다.
- 담당자 1, 2는 시그니처 변경 시 먼저 합의 후 반영한다.

### 7-2. `internal/service/command_service.py`

위험:

- 여러 서비스 파일의 진입점이라 병합 충돌이 잦을 수 있다.

대응:

- 담당자 2가 최종 소유한다.
- 새 명령 추가 전까지 다른 담당자는 직접 수정하지 않는다.

### 7-3. `cmd/mini_redis_cli/main.py`

위험:

- RESP3 표현, 출력 정책, 종료 코드 정책이 한 파일에 모인다.

대응:

- 담당자 4가 최종 소유한다.
- 프로토콜 변경이 필요하면 담당자 1과 합의 후 수정한다.

## 8. 완료 판정 기준

- 각 담당자는 자기 소유 파일에 대해 최소 단위 테스트 또는 수동 검증 경로를 제공해야 한다.
- 공동 조정 파일은 최종 소유 담당자가 병합 책임을 가진다.
- 전체 통합 경로는 `CLI -> Server -> Decoder -> Parser -> Validator -> Service -> Repository -> Encoder -> CLI` 순서로 실제 동작해야 한다.
- `SET`, `GET`, `DEL`, `EXPIRE`, `TTL`, `HELLO 3`이 end-to-end로 검증되어야 한다.

## 9. 브랜치 운영 방식

- 팀은 `main`, `dev`, 작업 브랜치 구조를 사용한다.
- 각 담당자는 작업 시작 전에 이슈를 만들고, 이슈 단위 작업 브랜치를 생성한다.
- 각 작업 브랜치는 먼저 `dev`에 병합한다.
- 통합 검증이 완료된 뒤 `dev`를 `main`에 병합한다.
- 공동 조정 파일 수정은 가능한 한 별도 이슈와 별도 브랜치로 분리한다.

예시 브랜치:

- `feat/12-request-decoder`
- `feat/18-expire-ttl-service`
- `feat/24-cli-output-policy`
- `test/31-cli-server-integration`

## 10. 권장 진행 방식

가장 안정적인 진행 방식은 다음과 같다.

1. 담당자 1과 담당자 2가 먼저 내부 인터페이스를 고정한다.
2. 담당자 3은 서버와 세션 처리 골격을 완성한다.
3. 담당자 4는 CLI와 테스트 골격을 먼저 만들고, 이후 통합 테스트를 붙인다.
4. 마지막 통합은 담당자 3과 담당자 4가 중심이 되어 진행한다.

이 방식이면 동일 파일 동시 수정이 줄고, 병렬 작업 효율이 가장 높다.

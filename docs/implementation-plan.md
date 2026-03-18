# 미니 Redis RESP3 구현 계획 문서

## 1. 문서 목적

이 문서는 미니 Redis 구현을 위한 모듈 구조, 파일 단위, 개발 순서, 테스트 범위를 정의한다.

본 문서는 [`requirements.md`](requirements.md), [`architecture.md`](architecture.md), [`api-spec.md`](api-spec.md), [`server-runtime.md`](server-runtime.md)를 실제 코드 구조로 구체화하는 것을 목적으로 한다.

## 2. 구현 원칙

- RESP3 프레임 처리 로직과 비즈니스 명령 로직을 분리한다.
- 저장소 로직과 TTL 로직을 분리한다.
- 테스트 가능성을 위해 시간과 저장소 의존성을 추상화한다.
- 1차 구현은 필수 명령과 RESP3 호환성에 집중한다.
- 프로덕션 확장을 고려해 모듈 간 경계를 명확히 유지한다.

## 3. 최상위 디렉터리 구조

권장 디렉터리 구조는 다음과 같다.

```text
cmd/
  mini_redis_server/
  mini_redis_cli/
internal/
  clock/
  command/
  config/
  expiration/
  guard/
  observability/
  protocol/
    resp/
  repository/
  server/
  service/
docs/
```

## 4. 모듈 구조 설계

### 4-1. `cmd`

역할:

- 서버와 CLI 실행 진입점 제공

예상 파일:

- `cmd/mini_redis_server/main.py`
- `cmd/mini_redis_cli/main.py`

### 4-2. `internal/config`

역할:

- 런타임 설정 로딩
- 기본값 관리
- 실행 인자와 환경 설정 해석

예상 파일:

- `internal/config/runtime_config.py`
- `internal/config/defaults.py`

### 4-3. `internal/clock`

역할:

- 현재 시각 추상화
- TTL 테스트 지원

예상 파일:

- `internal/clock/clock.py`
- `internal/clock/system_clock.py`
- `internal/clock/fake_clock.py`

### 4-4. `internal/command`

역할:

- 내부 명령 모델 정의
- RESP Array 기반 명령 파싱
- 명령 검증

예상 파일:

- `internal/command/command.py`
- `internal/command/parser.py`
- `internal/command/validator.py`
- `internal/command/errors.py`

### 4-5. `internal/service`

역할:

- 명령별 비즈니스 로직 수행

예상 파일:

- `internal/service/command_service.py`
- `internal/service/set_service.py`
- `internal/service/get_service.py`
- `internal/service/del_service.py`
- `internal/service/expire_service.py`
- `internal/service/ttl_service.py`

### 4-6. `internal/repository`

역할:

- 값 저장소와 TTL 저장소 인터페이스 및 인메모리 구현

예상 파일:

- `internal/repository/store_repository.py`
- `internal/repository/ttl_repository.py`
- `internal/repository/in_memory_store.py`
- `internal/repository/in_memory_ttl.py`

### 4-7. `internal/expiration`

역할:

- 만료 판단
- 만료 정리
- TTL 계산

예상 파일:

- `internal/expiration/expiration_manager.py`
- `internal/expiration/ttl_calculator.py`
- `internal/expiration/expiration_sweeper.py`

### 4-8. `internal/protocol/resp`

역할:

- RESP3 타입 모델 정의
- RESP 요청 디코딩
- RESP 응답 인코딩
- `HELLO 3` 협상 처리

예상 파일:

- `internal/protocol/resp/types.py`
- `internal/protocol/resp/request_decoder.py`
- `internal/protocol/resp/response_encoder.py`
- `internal/protocol/resp/messages.py`
- `internal/protocol/resp/hello_handler.py`

### 4-9. `internal/server`

역할:

- 서버 부트스트랩
- 연결 수락
- 세션 처리
- graceful shutdown

예상 파일:

- `internal/server/server.py`
- `internal/server/session_handler.py`
- `internal/server/shutdown.py`

### 4-10. `internal/guard`

역할:

- 연결 수 제한
- 요청 크기 제한
- RESP 프레임 자원 보호 정책 적용

예상 파일:

- `internal/guard/resource_guard.py`
- `internal/guard/limits.py`

### 4-11. `internal/observability`

역할:

- 로그와 메트릭 기록

예상 파일:

- `internal/observability/logger.py`
- `internal/observability/metrics.py`

## 5. 의존 관계 원칙

- `cmd`는 `config`, `server`, `protocol/resp`, `service`를 조립한다.
- `server`는 `protocol/resp`, `guard`, `service`, `observability`를 사용한다.
- `service`는 `repository`, `expiration`, `clock`을 사용한다.
- `expiration`은 `repository`, `clock`을 사용한다.
- `protocol/resp`는 RESP3 타입 모델과 명령 모델 사이의 변환을 담당한다.
- `repository`는 다른 비즈니스 계층을 알지 못해야 한다.

금지 원칙:

- `repository`가 `service`를 참조하면 안 된다.
- `command`가 `server` 또는 소켓 구현을 알면 안 된다.
- `cli`가 서버 내부 비즈니스 로직을 직접 호출하면 안 된다.

## 6. 파일 단위 상세 설계

### 6-1. 서버 진입점

`cmd/mini_redis_server/main.py`

책임:

- 설정 로딩
- 서버 인스턴스 생성
- 종료 시그널 처리
- graceful shutdown 시작

### 6-2. CLI 진입점

`cmd/mini_redis_cli/main.py`

책임:

- `--host`, `--port` 인자 파싱
- 세션 시작 시 `HELLO 3` 전송
- RESP3 명령 프레임 생성
- 서버 접속 및 요청 전송
- RESP3 응답 타입 판별
- 성공/실패 출력 정책 적용
- 종료 코드 반환

### 6-3. 파서와 검증기

`internal/command/parser.py`

책임:

- RESP Array 기반 명령을 내부 명령어와 인자 목록으로 변환
- 잘못된 명령 배열 감지

`internal/command/validator.py`

책임:

- 지원 명령 여부 확인
- 명령별 인자 개수 검증
- `EXPIRE seconds` 정수 검증

### 6-4. 서비스 계층

`internal/service/command_service.py`

책임:

- 명령 종류에 따라 하위 처리기 호출

개별 명령 서비스 파일 책임:

- `set_service.py`: 값 저장, 기존 TTL 제거
- `get_service.py`: 만료 검사 후 값 조회
- `del_service.py`: 만료 검사 후 삭제
- `expire_service.py`: TTL 설정
- `ttl_service.py`: TTL 계산 및 특수값 반환

### 6-5. 저장소 계층

`internal/repository/in_memory_store.py`

책임:

- 키-값 저장
- 값 조회
- 값 삭제

`internal/repository/in_memory_ttl.py`

책임:

- 키별 절대 만료 시각 저장
- TTL 조회
- TTL 삭제

### 6-6. 만료 처리 계층

`internal/expiration/expiration_manager.py`

책임:

- 키 만료 여부 판단
- 만료 시 값/TTL 동시 정리

`internal/expiration/ttl_calculator.py`

책임:

- 남은 TTL 계산
- 정수 초 단위 변환

`internal/expiration/expiration_sweeper.py`

책임:

- 백그라운드 주기적 정리 실행
- sweep interval 적용
- batch size 적용
- 시작/중지 제어

### 6-7. RESP3 프로토콜 계층

`internal/protocol/resp/request_decoder.py`

책임:

- RESP3 프레임 파싱
- Array, Blob String, Number, Null 등 타입 해석
- 최대 프레임 크기, 최대 배열 길이, 최대 중첩 깊이 검사와 연계

`internal/protocol/resp/response_encoder.py`

책임:

- RESP3 타입 직렬화
- Simple String, Blob String, Number, Null, Error, Map 인코딩

`internal/protocol/resp/hello_handler.py`

책임:

- `HELLO 3` 협상 처리
- 세션 프로토콜 모드 초기화
- 협상 응답용 메타데이터 생성

### 6-8. 서버 계층

`internal/server/server.py`

책임:

- 소켓 생성과 바인딩
- 연결 수락 루프

`internal/server/session_handler.py`

책임:

- 개별 연결 요청 읽기
- RESP 디코드 -> 협상 -> 명령 파싱 -> 검증 -> 서비스 -> RESP 인코드 흐름 실행
- 요청 단위 오류 격리

`internal/server/shutdown.py`

책임:

- 종료 신호 처리
- 새 연결 수락 중단
- 진행 중 세션 정리

### 6-9. 보호 및 관측 계층

`internal/guard/resource_guard.py`

책임:

- 연결 수 상한 확인
- 요청 크기, 배열 길이, 중첩 깊이 상한 확인
- 제한 초과 시 거부 정책 적용

`internal/observability/logger.py`

책임:

- 구조화 로그 기록

`internal/observability/metrics.py`

책임:

- 연결 수, 요청 수, 오류 수 카운트

## 7. 구현 순서

### 1단계. 기초 모듈 구성

- `config`
- `clock`
- `repository`

### 2단계. 명령 처리 기초 구현

- `command/parser`
- `command/validator`
- `service/command_service`

### 3단계. TTL 기능 구현

- `expiration`
- `service/expire_service`
- `service/ttl_service`

### 4단계. RESP3 프로토콜 구현

- `protocol/resp/types`
- `protocol/resp/request_decoder`
- `protocol/resp/response_encoder`
- `protocol/resp/hello_handler`

목표:

- 서버와 CLI가 RESP3 통신 계약과 `HELLO 3` 협상을 사용할 수 있게 한다.

### 5단계. 서버 구현

- `server/server`
- `server/session_handler`
- `guard/resource_guard`

목표:

- TCP 서버를 구동하고 RESP3 요청을 실제로 처리한다.

### 6단계. CLI 구현

- `cmd/mini_redis_cli`

목표:

- RESP3 단일 명령 실행형 CLI를 완성한다.

### 7단계. 운영 보강

- `observability`
- `shutdown`
- `expiration/expiration_sweeper`

### 8단계. 테스트 보강

- 단위 테스트
- 통합 테스트

## 8. 테스트 파일 구조

```text
tests/test_parser.py
tests/test_validator.py
tests/test_command_service.py
tests/test_expire_service.py
tests/test_ttl_service.py
tests/test_expiration_manager.py
tests/test_request_decoder.py
tests/test_response_encoder.py
tests/test_hello_handler.py
tests/test_server_integration.py
tests/test_cli_integration.py
```

핵심 테스트 항목:

- `SET` 후 `GET`
- `DEL` 성공/실패
- `EXPIRE` 성공/실패
- `TTL`의 `-1`, `-2`, 양수 응답
- 만료 후 자동 정리
- 잘못된 명령과 잘못된 인자 처리
- `HELLO 3` 협상 처리
- RESP3 타입 직렬화/역직렬화
- 연결 수/요청 크기 제한
- 서버 오류 격리
- 접근 없는 만료 키의 백그라운드 정리
- CLI 성공/실패 출력 구분
- CLI 종료 코드

## 9. 1차 구현 범위 체크리스트

- 서버가 `127.0.0.1:6379`에서 실행된다.
- CLI가 서버에 접속해 단일 명령을 전송할 수 있다.
- `HELLO 3` 협상 후 RESP3 세션이 성립한다.
- `SET`, `GET`, `DEL`, `EXPIRE`, `TTL`이 동작한다.
- RESP3 요청/응답 형식이 [`api-spec.md`](api-spec.md)와 일치한다.
- TTL 로직이 절대 만료 시각 기준으로 동작한다.
- 연결/요청 제한이 적용된다.
- 지연 삭제와 주기적 정리가 함께 동작한다.
- 기본 로그와 메트릭 기록이 가능하다.
- 잘못된 요청이 전체 서버 중단으로 이어지지 않는다.

## 10. 향후 확장 준비 사항

- `repository` 인터페이스를 유지해 영속성 저장소로 교체 가능하게 한다.
- `service` 경계를 유지해 복제 및 샤딩 전략을 추가할 수 있게 한다.
- `protocol/resp` 계층을 유지해 RESP3 확장 타입과 서버 푸시 메시지를 추가할 수 있게 한다.
- `observability`를 별도 모듈로 유지해 메트릭 시스템과 로깅 백엔드를 교체 가능하게 한다.
- `guard`를 별도 모듈로 유지해 운영 제한 정책을 동적으로 바꿀 수 있게 한다.

## 11. 자료구조 확장 구현 로드맵

### 11-1. 1차 구현

- `String`

### 11-2. 2차 구현

- `Hash`

예상 추가 파일:

- `internal/service/hash_service.*`
- `internal/repository/hash_repository.*`
- `internal/repository/in_memory_hash.*`

### 11-3. 3차 구현

- `List`

예상 추가 파일:

- `internal/service/list_service.*`
- `internal/repository/list_repository.*`
- `internal/repository/in_memory_list.*`

### 11-4. 4차 구현

- `Set`

예상 추가 파일:

- `internal/service/set_service.*`
- `internal/repository/set_repository.*`
- `internal/repository/in_memory_set.*`

### 11-5. 5차 구현

- `Sorted Set`

예상 추가 파일:

- `internal/service/zset_service.*`
- `internal/repository/zset_repository.*`
- `internal/repository/in_memory_zset.*`

### 11-6. 자료형 공통 확장 포인트

- `internal/command/validator.*`에 새 명령 검증 추가
- `internal/service/command_service.*`에 명령 분기 추가
- `internal/protocol/resp/messages.*`에 자료형 오류 메시지 추가
- `internal/repository`에 자료형별 저장 인터페이스 추가
- TTL 정책은 기존 키 단위 만료 로직을 그대로 재사용

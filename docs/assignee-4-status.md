# 미니 Redis 담당자 4 작업 상태 문서

## 1. 문서 목적

이 문서는 담당자 4가 맡은 범위에서 현재까지 구현한 내용, 아직 구현하지 못한 내용, 구현이 막힌 이유, 다음 구현에 필요한 선행 조건을 인수인계용으로 정리한 문서다.

기준 문서는 다음과 같다.

- `team-work-allocation.md`
- `implementation-plan.md`
- `api-spec.md`
- `server-runtime.md`

## 2. 담당자 4 범위 기준

담당자 4의 공식 범위는 다음과 같다.

- CLI 구현
- 설정 로딩
- 테스트 뼈대 작성
- 통합 검증과 수용 기준 점검

공식 소유 파일은 다음과 같다.

- `cmd/mini_redis_cli/main.py`
- `internal/config/runtime_config.py`
- `internal/config/defaults.py`
- `internal/clock/clock.py`
- `internal/clock/system_clock.py`
- `internal/clock/fake_clock.py`
- `tests/test_imports.py`
- 향후 추가될 `tests/test_*.py` 파일 전반

## 3. 현재 구현한 내용

### 3-1. CLI

대상 파일:

- `cmd/mini_redis_cli/main.py`

현재 반영한 내용:

- `--host`, `--port` 인자 파싱
- 명령 누락 시 사용법 오류 출력과 종료 코드 `2` 반환
- 연결 실패 또는 통신 실패 시 종료 코드 `3` 반환
- 서버 오류 응답 시 종료 코드 `4` 반환
- 성공 응답 시 종료 코드 `0` 반환
- 세션 시작 시 `HELLO 3` 요청 프레임 송신
- 단일 명령 요청 프레임 생성
- RESP 응답의 일부 타입에 대한 임시 파싱 및 렌더링
  - Simple String
  - Blob String
  - Number
  - Null
  - Error
  - Map
- `python3 cmd/mini_redis_cli/main.py` 형태의 직접 실행을 위한 import 경로 보정

설명:

- 현재 CLI는 담당자 1의 공식 RESP 계층이 아직 고정되지 않았기 때문에, 최소 동작 검증을 위해 CLI 내부에 임시 RESP 인코딩/디코딩 로직을 넣었다.
- 이 구현은 최종 확정본이 아니라 통합 전 임시 골격이다.

### 3-2. 설정

대상 파일:

- `internal/config/defaults.py`
- `internal/config/runtime_config.py`

현재 반영한 내용:

- 문서 기준 기본 네트워크 값 유지
  - host `127.0.0.1`
  - port `6379`
- 기본 타임아웃 값 유지
  - connect `3`
  - read `5`
  - write `5`
  - idle `5`
- 기본 제한값 유지
  - max connections `100`
  - max request size `4KB`
  - max array items `64`
  - max RESP depth `8`
  - max blob size `4KB`
- 운영 문서에 있던 항목을 설정 객체에 추가
  - expiration sweep interval
  - expiration sweep batch size
  - expiration sweep enabled
  - log level
- CLI 종료 코드 상수 추가
- CLI에서 host/port만 덮어쓸 수 있도록 `with_connection_target()` 추가

### 3-3. Clock

대상 파일:

- `internal/clock/clock.py`
- `internal/clock/system_clock.py`
- `internal/clock/fake_clock.py`

현재 상태:

- clock 계층 코드는 기존 구현을 그대로 유지했다.
- 현재 단계에서 구조 변경은 필요하지 않다고 판단했다.
- 대신 테스트를 추가해 현재 동작을 고정했다.

검증된 내용:

- `FakeClock` 초기 시각 주입
- `FakeClock.advance()` 동작
- `SystemClock.now()`가 현재 시각 범위 안의 값을 반환하는지 확인

### 3-4. 테스트

대상 파일:

- `tests/test_imports.py`
- `tests/test_config.py`
- `tests/test_clock.py`
- `tests/test_cli_main.py`

보조 파일:

- `tests/support.py`

현재 반영한 내용:

- 담당자 4 범위만 독립적으로 import 가능한지 확인하는 smoke test 추가
- 설정 기본값 테스트 추가
- clock 동작 테스트 추가
- CLI 단위 테스트 추가
  - 기본 인자 파싱
  - 명령 누락 시 종료 코드
  - 연결 실패 시 종료 코드
  - `HELLO 3` 후 명령 전송 순서
  - 서버 오류 응답 처리

설명:

- 실제 로컬 서버 소켓 바인딩은 샌드박스에서 제한될 수 있어, CLI 테스트는 가짜 소켓 기반으로 작성했다.
- 이 테스트는 CLI가 서버와 통신하는 호출 순서와 종료 코드 정책을 우선 검증한다.

## 4. 아직 구현하지 못한 내용

### 4-1. CLI의 공식 RESP 계층 연동

현재 미구현 내용:

- CLI가 `internal/protocol/resp/*`의 공식 인코더/디코더를 사용하도록 연결하는 작업

구현하지 못한 이유:

- `internal/protocol/resp/request_decoder.py`
- `internal/protocol/resp/response_encoder.py`
- `internal/service/command_service.py`

위 핵심 파일이 아직 스텁 상태이거나 인터페이스가 고정되지 않았다.

구현을 위해 필요한 내용:

- 담당자 1이 최종 RESP 요청/응답 모델을 고정해야 한다.
- 담당자 1이 오류 메시지 상수와 응답 타입 표현 방식을 확정해야 한다.
- CLI가 프로토콜 계층을 직접 재사용할지, 별도 경량 클라이언트 인코더/디코더를 둘지 팀 합의가 필요하다.

### 4-2. 실제 서버와 붙는 end-to-end 통합 테스트

현재 미구현 내용:

- `CLI -> Server -> Decoder -> Parser -> Validator -> Service -> Repository -> Encoder -> CLI` 전체 경로 통합 테스트

구현하지 못한 이유:

- 담당자 3의 서버 실행 경로와 세션 처리 흐름이 아직 확정되지 않았다.
- 담당자 1과 담당자 2의 프로토콜/서비스 구현이 아직 완료되지 않았다.
- 현재 서버 엔트리포인트와 import 경로도 안정적으로 고정된 상태가 아니다.

구현을 위해 필요한 내용:

- 담당자 3이 서버 실행 명령과 세션 처리 정책을 고정해야 한다.
- 담당자 1이 디코더/인코더를 완료해야 한다.
- 담당자 2가 `SET`, `GET`, `DEL`, `EXPIRE`, `TTL` 서비스 경로를 완료해야 한다.
- 최소 1개의 정상 실행 가능한 서버 부트스트랩 경로가 필요하다.

### 4-3. CLI 출력 형식의 최종 확정

현재 미구현 내용:

- Map, Null, Number 등 응답을 사용자에게 어떻게 보여줄지 최종 정책 확정

구현하지 못한 이유:

- 문서에는 성공/실패와 종료 코드 규칙은 있지만, 사람이 읽는 출력 예시는 충분히 구체적이지 않다.
- 서버 응답 타입 표현도 아직 팀 전체에서 고정되지 않았다.

구현을 위해 필요한 내용:

- 담당자 1과 응답 타입별 렌더링 예시 합의
- 담당자 3과 서버 오류 응답 전달 방식 합의

### 4-4. `mini-redis-cli` 패키징/실행 경로 정리

현재 미구현 내용:

- 사용자 문서에 나온 `mini-redis-cli` 명령 자체를 프로젝트에서 바로 제공하는 작업

구현하지 못한 이유:

- 패키징 설정 파일이나 실행 스크립트 구조가 아직 없다.
- 현재는 `python3 cmd/mini_redis_cli/main.py` 수준의 직접 실행만 임시 지원한다.

구현을 위해 필요한 내용:

- 팀이 패키징 방식 또는 실행 진입점 방식을 결정해야 한다.
- 최소한 `pyproject.toml` 또는 동등한 실행 설정이 필요하다.

### 4-5. 프로젝트 전체 Python 버전 정렬

현재 미구현 내용:

- 저장소 전체가 동일한 Python 최소 버전 가정을 따르도록 정리하는 작업

구현하지 못한 이유:

- 담당자 4 범위 밖의 일부 파일이 Python 3.10 이상 문법을 사용하고 있다.
- 현재 로컬 `python3`는 3.9.6이라 전체 프로젝트를 바로 실행하면 import 단계에서 깨지는 파일이 있다.

구현을 위해 필요한 내용:

- 팀 차원의 최소 Python 버전 합의
또는
- 전 코드베이스의 타입 표기와 실행 호환성 정리

## 5. 현재 수정한 파일 목록

### 5-1. 담당자 4 범위 안에서 수정한 파일

- `cmd/mini_redis_cli/main.py`
- `internal/config/defaults.py`
- `internal/config/runtime_config.py`
- `tests/test_imports.py`
- `tests/test_config.py`
- `tests/test_clock.py`
- `tests/test_cli_main.py`

설명:

- 위 파일들은 담당자 4의 공식 소유 파일 또는 담당자 4가 추가한 `tests/test_*.py` 파일이다.

### 5-2. 담당자 4 범위 안에서 검증만 하고 수정하지 않은 파일

- `internal/clock/clock.py`
- `internal/clock/system_clock.py`
- `internal/clock/fake_clock.py`

설명:

- 현재 구현이 충분해서 코드 수정은 하지 않았고, 테스트로만 동작을 고정했다.

## 6. 우리 범위가 아니었지만 수정한 파일 목록과 이유

엄밀한 파일 소유권 기준에서 담당자 4 범위 밖이지만 수정한 파일은 다음과 같다.

### 6-1. 문서 파일

- `docs/assignee-4-status.md`

수정 이유:

- 기존 체크리스트 문서보다 현재 구현 상태와 남은 작업을 직접 전달하는 문서가 더 협업에 유효하다고 판단했다.

### 6-2. 제거한 문서 파일

- `docs/assignee-4-checklist.md`

수정 이유:

- 체크리스트는 실제 구현 상태를 충분히 설명하지 못했고, 완료 여부를 오해하게 만들 가능성이 있어 상태 문서로 교체했다.

### 6-3. 테스트 보조 파일

- `tests/support.py`

수정 이유:

- `cmd` 디렉터리 이름이 Python 표준 라이브러리 `cmd`와 충돌할 수 있어, 테스트에서 CLI 모듈을 안정적으로 로드하기 위한 보조 로더가 필요했다.
- `tests/test_*.py` 범위에는 포함되지 않지만 담당자 4 테스트를 안정적으로 실행하기 위해 추가했다.

## 7. 현재 기준 검증 결과

실행한 검증:

- `python3 -m unittest discover -s tests -q`

현재 결과:

- 담당자 4 범위 테스트 11개 통과

주의 사항:

- 이 검증은 담당자 4 범위만 대상으로 한다.
- 실제 서버 전체 통합 검증이 아니라, CLI 골격과 설정/clock/테스트 기반이 정상 동작하는지 확인한 상태다.

## 8. 다음 작업 권장 순서

1. 담당자 1이 RESP 인코더/디코더와 오류 모델을 고정한다.
2. 담당자 2가 서비스 반환 모델과 필수 명령 구현을 완료한다.
3. 담당자 3이 서버 실행 경로와 세션 흐름을 고정한다.
4. 담당자 4가 현재 임시 CLI RESP 로직을 팀 공용 인터페이스로 교체한다.
5. 담당자 4가 실제 서버 대상 통합 테스트와 end-to-end 검증을 추가한다.

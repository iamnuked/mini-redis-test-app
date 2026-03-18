# mini-redis

`mini-redis`는 Redis의 핵심 개념을 학습하기 위한 RESP3 기반 미니 서버/CLI 프로젝트입니다.

현재 프로젝트는 다음 범위를 중심으로 구현되어 있습니다.

- TCP 소켓 기반 서버
- CLI 클라이언트
- RESP3 `HELLO 3` 협상
- 문자열 키-값 저장
- `SET`, `GET`, `DEL`, `EXPIRE`, `TTL`
- TTL 지연 삭제 및 백그라운드 주기적 정리

## 주요 특징

- 지원 명령 집합에 한정해 Redis RESP3 요청/응답 규약과 호환되는 것을 목표로 합니다.
- 서버와 CLI가 분리된 구조로 구현되어 있습니다.
- 명령 파싱, 검증, 서비스, 저장소, 만료 처리 계층이 분리되어 있습니다.
- 테스트 중심으로 개발되어 현재 단위 테스트와 통합 테스트가 포함되어 있습니다.

## 현재 범위

이 프로젝트는 학습용 구현입니다.

- 단일 프로세스
- 인메모리 저장소
- 영속성 없음
- 복제, 클러스터링, 샤딩 없음
- 1차 구현 자료형은 문자열만 지원

향후 확장 로드맵은 `Hash`, `List`, `Set`, `Sorted Set` 순서를 기준으로 정리되어 있습니다.

## 빠른 시작

### 1. 가상환경 생성 및 의존성 설치

Windows PowerShell 예시:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### 2. 서버 실행

```powershell
python -m cmd.mini_redis_server.main
```

기본 서버 주소/포트는 문서에 정의된 런타임 설정을 따릅니다.

### 3. CLI 단일 명령 실행

```powershell
python -m cmd.mini_redis_cli.main GET mykey
python -m cmd.mini_redis_cli.main SET mykey hello
python -m cmd.mini_redis_cli.main TTL mykey
```

호스트와 포트를 직접 지정할 수도 있습니다.

```powershell
python -m cmd.mini_redis_cli.main --host 127.0.0.1 --port 6379 GET mykey
```

### 4. CLI REPL 실행

```powershell
python -m cmd.mini_redis_cli.main
```

실행 후 예시:

```text
mini-redis> SET mykey hello
OK
mini-redis> GET mykey
hello
mini-redis> TTL mykey
-1
mini-redis> quit
```

REPL에서는 다음 동작을 지원합니다.

- 빈 줄 입력 무시
- `exit`, `quit` 입력 시 종료
- 개별 명령 오류가 발생해도 다음 명령 계속 입력 가능

현재 서버는 연결당 요청 1개를 처리하므로, REPL은 사용자에게는 연속 입력처럼 보이지만 내부적으로는 명령마다 새 연결을 사용합니다.

## 테스트 실행

전체 테스트:

```powershell
python -m pytest -q
```

CLI 테스트만 실행:

```powershell
python -m pytest -q tests\test_cli_main.py
```

## 프로젝트 구조

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
tests/
```

## 아키텍처 개요

상위 흐름은 다음과 같습니다.

`CLI -> Server Listener -> Session Handler -> Protocol Handler -> Command Service -> Repository / Expiration -> Response Encoder -> CLI`

주요 계층 역할:

- `cmd`: 서버/CLI 실행 진입점
- `internal/protocol/resp`: RESP3 파싱/직렬화
- `internal/command`: 명령 모델, 파싱, 검증
- `internal/service`: 비즈니스 로직
- `internal/repository`: 인메모리 저장소
- `internal/expiration`: TTL 계산과 만료 정리
- `internal/server`: 연결 수락, 세션 처리, shutdown
- `internal/guard`: 요청 크기/연결 수 제한
- `internal/observability`: 로그/메트릭

## 지원 명령

현재 필수 지원 명령은 다음과 같습니다.

- `HELLO 3`
- `SET key value`
- `GET key`
- `DEL key`
- `EXPIRE key seconds`
- `TTL key`

## 입력 명령 예시

CLI 단일 명령 실행 예시:

```powershell
python -m cmd.mini_redis_cli.main SET mykey hello
python -m cmd.mini_redis_cli.main GET mykey
python -m cmd.mini_redis_cli.main EXPIRE mykey 10
python -m cmd.mini_redis_cli.main TTL mykey
python -m cmd.mini_redis_cli.main DEL mykey
```

REPL 내부 입력 예시:

```text
mini-redis> SET mykey hello
mini-redis> GET mykey
mini-redis> EXPIRE mykey 10
mini-redis> TTL mykey
mini-redis> DEL mykey
mini-redis> quit
```

참고:

- CLI는 내부적으로 각 명령 전에 `HELLO 3`을 수행합니다.
- 사용자는 일반적으로 `HELLO 3`을 직접 입력하지 않고, CLI가 자동으로 처리하도록 사용하면 됩니다.

## 문서 안내

자세한 내용은 아래 문서를 기준으로 확인할 수 있습니다.

- [요구사항 정의서](docs/requirements.md)
- [아키텍처 설계 문서](docs/architecture.md)
- [RESP3 API 명세서](docs/api-spec.md)
- [서버 런타임 설정 문서](docs/server-runtime.md)
- [구현 계획 문서](docs/implementation-plan.md)
- [협업 규칙 문서](docs/collaboration-rules.md)
- [업무 분장 문서](docs/team-work-allocation.md)
- [Git 워크플로우 가이드](docs/git-workflow-guide.md)

## 협업 및 브랜치 전략

이 저장소는 다음 전략을 사용합니다.

- `main`: 안정 브랜치
- `dev`: 통합 개발 브랜치
- 작업 브랜치: 이슈 기반 feature branch

자세한 규칙은 [협업 규칙 문서](docs/collaboration-rules.md)와 [Git 워크플로우 가이드](docs/git-workflow-guide.md)를 참고하세요.

## 참고 사항

- 이 프로젝트는 학습용 mini-redis입니다.
- 문서가 구현보다 우선합니다.
- 세부 명세는 `docs` 문서를 기준으로 관리합니다.

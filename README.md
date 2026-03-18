# mini-redis

> Compatibility note:
> The server now accepts RESP2-compatible default connections for `redis-py` and can switch to RESP3 after `HELLO 3`.
> The CLI still starts each command by sending `HELLO 3`, so CLI behavior remains RESP3-first.

`mini-redis`는 Redis의 핵심 개념을 학습하기 위한 RESP3 기반 미니 서버/CLI 프로젝트입니다.

현재 프로젝트는 다음 범위를 중심으로 구현되어 있습니다.

- TCP 소켓 기반 서버
- CLI 클라이언트
- Arena 비교용 HTTP gateway 및 대시보드
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
$env:PYTHONPATH = (Get-Location).Path
python .\cmd\mini_redis_server\main.py
```

기본 서버 주소/포트는 문서에 정의된 런타임 설정을 따릅니다.

### 3. CLI 단일 명령 실행

```powershell
$env:PYTHONPATH = (Get-Location).Path
python .\cmd\mini_redis_cli\main.py GET mykey
python .\cmd\mini_redis_cli\main.py HSET user name mini
python .\cmd\mini_redis_cli\main.py LRANGE queue 0 -1
```

### 4. CLI REPL 실행

```powershell
$env:PYTHONPATH = (Get-Location).Path
python .\cmd\mini_redis_cli\main.py
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

현재 서버는 하나의 연결에서 여러 요청을 연속 처리할 수 있습니다. 현재 CLI REPL은 명령마다 새 연결을 사용하지만, 서버 자체는 지속 연결 세션을 지원합니다.

## 테스트 실행

전체 테스트:

```powershell
python -m pytest -q
```

CLI 테스트만 실행:

```powershell
python -m pytest -q tests\test_cli_main.py
```

Arena 테스트만 실행:

```powershell
python -m pytest -q tests\arena
```

## 프로젝트 구조

```text
cmd/
  arena_gateway/
  arena_lane_a/
  arena_lane_b/
  mini_redis_server/
  mini_redis_cli/
internal/
  arena/
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
web/
```

## 아키텍처 개요

상위 흐름은 다음과 같습니다.

`CLI -> Server Listener -> Session Handler -> Protocol Handler -> Command Service -> Repository / Expiration -> Response Encoder -> CLI`

주요 계층 역할:

- `cmd`: 서버/CLI 실행 진입점
- `cmd/arena_gateway`: Arena HTTP gateway 실행 진입점
- `cmd/arena_lane_a`: Redis + Mongo lane 실행 진입점
- `cmd/arena_lane_b`: Mongo only lane 실행 진입점
- `internal/arena`: Arena 비교 로직, 시나리오, 이벤트, gateway, lane 서비스
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
$env:PYTHONPATH = (Get-Location).Path
python .\cmd\mini_redis_cli\main.py SET mykey hello
python .\cmd\mini_redis_cli\main.py HSET user name mini
python .\cmd\mini_redis_cli\main.py SMEMBERS tags
python .\cmd\mini_redis_cli\main.py ZRANGE ranking 0 -1
python .\cmd\mini_redis_cli\main.py TTL mykey
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
- [Arena 시작 문서](docs/arena/README.md)
- [Arena 최종 방향](docs/arena/final-direction.md)
- [Arena mini-redis 연동 메모](docs/arena/mini-redis-integration.md)
- [Arena benchmark 구조](docs/arena/benchmark-architecture.md)
- [Arena 구현 참조 문서](docs/arena/implementation-reference.md)
- [Arena 로컬 Mongo 실행 가이드](docs/arena/local-mongo-runbook.md)

## 참고 사항

- 이 프로젝트는 학습용 mini-redis입니다.
- 문서가 구현보다 우선합니다.
- 세부 명세는 `docs` 문서를 기준으로 관리합니다.

## Arena 빠른 시작

Arena는 다음 구성으로 동작합니다.

- `gateway`
- `lane-a` (`mini-redis + MongoDB`)
- `lane-b` (`MongoDB only`)
- `mini-redis`

속도 비교 기준 구조는 [docs/arena/benchmark-architecture.md](docs/arena/benchmark-architecture.md)를 따른다.

### 1. 로컬 스크립트로 전체 실행

Mongo 데이터 디렉터리를 저장소 내부 `.local/arena`에 두고 전체 stack을 한 번에 올리려면:

```bash
./scripts/arena-local-up.sh
./scripts/arena-local-status.sh
```

내릴 때:

```bash
./scripts/arena-local-down.sh
```

세부 기준은 [docs/arena/local-mongo-runbook.md](docs/arena/local-mongo-runbook.md)를 따른다.

### 2. Docker Compose로 전체 실행

```bash
docker compose -f deploy/docker-compose.arena.yml up --build
```

실행 후 포트:

- `8000`: gateway + dashboard
- `8001`: lane-a
- `8002`: lane-b
- `6379`: mini-redis
- `27017`: mongo-a
- `27018`: mongo-b

브라우저에서 `http://127.0.0.1:8000`을 열면 대시보드를 확인할 수 있습니다.

### 3. 로컬에서 개별 실행

`mini-redis`:

```bash
PYTHONPATH=. python cmd/mini_redis_server/main.py
```

`lane-a`:

```bash
PYTHONPATH=. ARENA_REDIS_BACKEND=redis_py ARENA_MONGO_BACKEND=pymongo MONGO_URI=mongodb://127.0.0.1:27017 MONGO_DB_NAME=arena_lane_a python cmd/arena_lane_a/main.py
```

`lane-b`:

```bash
PYTHONPATH=. ARENA_MONGO_BACKEND=pymongo MONGO_URI=mongodb://127.0.0.1:27018 MONGO_DB_NAME=arena_lane_b python cmd/arena_lane_b/main.py
```

`gateway`:

```bash
PYTHONPATH=. ARENA_LANE_A_BASE_URL=http://127.0.0.1:8001 ARENA_LANE_B_BASE_URL=http://127.0.0.1:8002 python cmd/arena_gateway/main.py
```

# 01. Project Map

## 핵심 질문

- 이 저장소는 왜 `mini-redis`와 Arena 두 부분으로 나뉘는가
- 어떤 디렉터리가 서버 코어이고, 어떤 디렉터리가 응용 앱인가

## 먼저 볼 파일

- `README.md`
- `cmd/mini_redis_server/main.py`
- `cmd/mini_redis_cli/main.py`
- `internal/server/server.py`
- `internal/arena/api/app.py`
- `web/arena_dashboard/index.html`

## 큰 그림

이 저장소는 한 문장으로 요약하면 이렇다.

> Redis의 핵심 개념을 직접 구현한 서버를 만들고, 그 서버를 실제 캐시처럼 활용하는 비교 앱까지 연결한 프로젝트

그래서 구조를 읽을 때는 두 단계로 나누면 된다.

1. `mini-redis`
   - RESP 기반 서버
   - 자료구조, TTL, eviction, CLI
2. `Arena`
   - `mini-redis + MongoDB`와 `MongoDB Only` 비교
   - gateway, lane, scenario, dashboard

## 디렉터리 지도

```text
cmd/        실행 진입점
internal/   핵심 구현
web/        대시보드
scripts/    로컬 실행 도구
tests/      테스트
docs/       설계 문서
Lesson/     학습 자료
```

## 왜 이 구조가 좋은가

- 실행 파일과 구현이 분리된다.
- protocol, command, service, repository가 분리돼 읽기 쉽다.
- Arena가 mini-redis를 “직접 import하는 라이브러리”가 아니라 “실제 서버”처럼 쓴다.

## 직접 해볼 것

1. `cmd/mini_redis_server/main.py`를 열고 서버가 어디서 시작되는지 확인한다.
2. `cmd/arena_gateway/main.py`를 열고 Arena가 별도 앱으로 시작된다는 점을 확인한다.
3. `README.md`의 다이어그램과 실제 디렉터리를 대조해본다.

# 07. CLI and Client Compatibility

## 핵심 질문

- 왜 CLI만 잘 되면 끝이 아닌가
- 외부 client와 호환된다는 것은 무엇을 의미하는가

## 먼저 볼 파일

- `cmd/mini_redis_cli/main.py`
- `docs/api-spec.md`
- `tests/test_redis_py_compatibility.py`
- `internal/arena/lane/redis_client.py`

## CLI

CLI는 이 프로젝트의 가장 직접적인 진입점이다.

- 단일 명령 실행
- REPL
- 종료 코드
- 성공/오류 렌더링

이 계층을 통해 사용자는 서버를 가장 빠르게 체험할 수 있다.

## 왜 `redis-py`가 중요한가

Arena는 `mini-redis`를 “우리 내부 객체”가 아니라 “외부 Redis 서버”처럼 사용한다. 그래서 `redis-py`와 붙는다는 것은 단순 편의가 아니라 프로젝트의 확장 가능성을 보여주는 증거다.

이 지점에서 배우는 것:

- 프로토콜 호환성의 실제 의미
- 클라이언트 재사용과 connection lifecycle
- 실험 앱이 코어 서버를 어떻게 소비하는가

## Arena에서의 활용

lane-a는 `redis-py` client를 통해 `mini-redis`에 붙는다. 이 경계 덕분에 Arena는 “같은 저장소 안의 함수 호출”이 아니라 “실제 네트워크 캐시 호출”을 비교하게 된다.

## 직접 해볼 것

1. CLI로 `SET/GET/HSET/HGET`을 수행한다.
2. Arena를 띄운 뒤 lane-a가 `redis-py`로 어떤 명령을 보내는지 확인한다.
3. `redis client 재사용`이 왜 공정성 측면에서 중요한지 설명해본다.

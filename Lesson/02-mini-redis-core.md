# 02. mini-redis Core

## 핵심 질문

- 이 프로젝트에서 “mini-redis”의 최소 핵심은 무엇인가
- 단순 딕셔너리 서버와 무엇이 다른가

## 먼저 볼 파일

- `internal/server/server.py`
- `internal/server/session_handler.py`
- `internal/service/command_service.py`
- `internal/repository/in_memory_store.py`
- `internal/repository/in_memory_ttl.py`

## 핵심 개념

`mini-redis`의 핵심은 세 가지다.

1. 네트워크를 통해 명령을 받는다.
2. 명령을 타입 있는 데이터 구조로 실행한다.
3. TTL과 memory control까지 포함해 Redis다운 동작을 보여준다.

이 프로젝트는 “메모리에 값 저장”에서 끝나지 않고, “명령을 받아 처리하는 서버”라는 Redis의 본질을 따라간다.

## 코어 흐름

서버는 대략 이렇게 움직인다.

1. TCP 연결 수락
2. 세션에서 요청 읽기
3. RESP 디코딩
4. 명령 파싱/검증
5. 서비스 실행
6. 응답 인코딩

이때 `command_service.py`가 핵심 허브다. 대부분의 명령이 여기서 자료형 검사, TTL 검사, repository 접근, 응답 생성까지 이어진다.

## 왜 중요한가

이 구조를 이해하면 이후 자료형 확장도 같은 패턴으로 읽을 수 있다.

- `SET/GET/DEL`을 이해하면
- `HSET/HGET`
- `LPUSH/LRANGE`
- `SADD/SMEMBERS`
- `ZADD/ZRANGE`
도 같은 틀로 해석할 수 있다.

## 직접 해볼 것

1. `command_service.py`에서 `SET`과 `GET` 코드를 먼저 읽는다.
2. `in_memory_store.py`를 열어 실제 값이 어떻게 저장되는지 본다.
3. `DBSIZE`, `INFO MEMORY`, `FLUSHDB`가 왜 core에 포함되는지 생각해본다.

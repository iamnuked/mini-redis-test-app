# 05. Data Structures and Storage

## 핵심 질문

- Redis는 왜 자료구조 서버라고 불리는가
- 이 프로젝트는 그 개념을 어떻게 단순화해서 담았는가

## 먼저 볼 파일

- `internal/repository/value_entry.py`
- `internal/repository/store_repository.py`
- `internal/repository/in_memory_store.py`
- `internal/service/command_service.py`

## 저장 모델

이 프로젝트는 각 키를 `ValueEntry`로 저장한다. 핵심은 “키 하나에 타입 하나”다.

예:

- `STRING`
- `HASH`
- `LIST`
- `SET`
- `ZSET`

이 방식 덕분에 서비스 계층에서 타입 검사를 명시적으로 수행할 수 있다.

## 왜 자료구조가 중요한가

문자열만 있으면 key-value store지만, 자료구조가 있으면 command server가 된다.

예:

- `HSET/HGET`
  - 문서형 데이터
- `LPUSH/LRANGE`
  - queue, feed
- `SADD/SMEMBERS`
  - membership, tag
- `ZADD/ZRANGE`
  - ranking, score

이 프로젝트는 그 모든 걸 완전한 Redis 수준으로 구현하지는 않지만, 핵심 개념이 어떻게 모델링되는지는 보여준다.

## Arena와의 연결

Arena는 지금 문자열과 hash 명령을 특히 많이 활용한다. 그래서 `mini-redis`의 자료형 모델이 단순 예제를 넘어 실제 비교 앱까지 이어진다.

## 직접 해볼 것

1. `SET/GET` 경로와 `HSET/HGET` 경로를 비교한다.
2. `WRONGTYPE`를 일부러 발생시켜 본다.
3. 같은 key에 `String`과 `Hash`가 동시에 들어갈 수 없는 이유를 설명해본다.
